"""Deterministic kirana conversation agent.

Gemini (nlu.py) only interprets language. This module owns cart state,
clarifications, substitutions, bills and when confirm_order is called.
"""

import nlu
import order_engine
import resolver


_SESSIONS = {}


def reset_sessions():
    _SESSIONS.clear()


def get_agent(customer_id, session_id=None, interpret_fn=None):
    key = (customer_id, session_id or customer_id)
    agent = _SESSIONS.get(key)
    if agent is None or (interpret_fn is not None and agent.interpret_fn is not interpret_fn):
        agent = KiranaAgent(
            customer_id,
            session_id=session_id,
            interpret_fn=interpret_fn,
        )
        _SESSIONS[key] = agent
    return agent


def _rupees(amount):
    if isinstance(amount, (int, float)) and float(amount).is_integer():
        return "Rs." + str(int(amount))
    return "Rs." + str(amount)


def _mention_clause(mention):
    parts = []
    quantity = mention.get("quantity")
    unit = mention.get("unit")
    if quantity is not None:
        parts.append(str(quantity))
        if unit:
            parts.append(str(unit))
    parts.append(mention.get("description") or "")
    return " ".join(part for part in parts if part).strip()


def _cart_line(resolved):
    product = order_engine.get_product(resolved["sku"])
    quantity = resolved["quantity"]
    return {
        "sku": product["sku"],
        "item": product["item"],
        "quantity": quantity,
        "unit": product["unit"],
        "price": product["price"],
        "line_total": product["price"] * quantity,
    }


class KiranaAgent:
    def __init__(self, customer_id, session_id=None, interpret_fn=None):
        self.customer_id = customer_id
        self.session_id = session_id or customer_id
        self.interpret_fn = interpret_fn or nlu.interpret
        self._reset_draft()

    def _reset_draft(self, status="collecting"):
        self.cart = []
        self.pending_clarifications = []
        self.pending_substitutions = []
        self.unsupported = []
        self.recent_messages = []
        self.status = status
        self.order_id = None
        self.bill_shown = False
        self.last_notes = []

    def handle(self, message):
        customer = order_engine.get_customer(self.customer_id)
        if customer is None:
            return self._snapshot("I could not find that customer.")

        text = (message or "").strip()
        if not text:
            return self._snapshot("Please send the items you need.")

        parsed = self._interpret(text)
        if not parsed.get("ok"):
            return self._snapshot(
                "I didn't catch that. Please list the items, or say confirm or cancel."
            )

        intent = parsed["intent"]
        if self.status == "confirmed" and intent in ("confirm", "cancel"):
            if intent == "cancel":
                return self._snapshot(
                    "Order "
                    + (self.order_id or "")
                    + " is already confirmed, so it cannot be cancelled here."
                )
            existing = order_engine.get_order(self.order_id) if self.order_id else None
            if existing is not None:
                return self._snapshot(self._placed_reply(existing))
        if self.status == "confirmed" and intent in (
            "new_order",
            "usual_order",
            "add_items",
        ):
            self._reset_draft()
        if self.status == "awaiting_owner_approval" and intent not in (
            "cancel",
            "confirm",
        ):
            return self._snapshot(
                "This order is already waiting for Ramesh. Say cancel if you want to withdraw it."
            )

        self.last_notes = []
        self.recent_messages.append({"role": "user", "text": text})

        if intent == "cancel":
            reply = self._cancel()
        elif intent == "confirm":
            self._apply_mentions(parsed)
            reply = self._confirm()
        elif intent == "usual_order":
            reply = self._load_usual_order()
        elif intent in ("clarification", "accept_substitution", "reject_substitution"):
            reply = self._handle_follow_up(intent, parsed, text)
        else:
            if intent == "new_order" and self.status in (
                "awaiting_customer_confirmation",
                "collecting",
            ) and not self.cart and not self.pending_clarifications:
                pass
            self._apply_mentions(parsed)
            reply = self._compose_reply()

        self.recent_messages.append({"role": "assistant", "text": reply})
        self.recent_messages = self.recent_messages[-8:]
        return self._snapshot(reply)

    def _interpret(self, text):
        try:
            return self.interpret_fn(text, context=self._nlu_context())
        except TypeError:
            return self.interpret_fn(text)

    def _nlu_context(self):
        pending = []
        for item in self.pending_clarifications:
            pending.append({
                "query": item["query"],
                "options": [candidate["item"] for candidate in item["candidates"]],
            })
        substitution = None
        if self.pending_substitutions:
            first = self.pending_substitutions[0]
            substitution = {
                "item": first["item"],
                "options": [option["item"] for option in first["substitutes"]],
            }
        return {
            "cart": [
                {
                    "description": line["item"],
                    "quantity": line["quantity"],
                    "unit": line["unit"],
                }
                for line in self.cart
            ],
            "pending_clarifications": pending,
            "pending_substitution": substitution,
            "recent_messages": list(self.recent_messages[-4:]),
        }

    def _apply_mentions(self, parsed):
        for mention in parsed.get("mentions") or []:
            action = mention.get("action") or "add"
            if action == "remove":
                self._remove_description(mention["description"])
            elif action == "set_quantity":
                self._set_quantity(mention)
            else:
                self._add_description(mention)

    def _add_description(self, mention, action="add"):
        clause = _mention_clause(mention)
        resolved = resolver.resolve_mention(clause)
        self._ingest_resolved(resolved, action=action, raw=mention["description"])

    def _ingest_resolved(self, resolved, action="add", raw=None):
        status = resolved.get("status")
        if status == "unsupported":
            label = raw or resolved.get("query") or "that item"
            if label not in self.unsupported:
                self.unsupported.append(label)
            self.last_notes.append(
                label
                + " is not in our catalogue, so I have not added it."
            )
            return

        if status == "ambiguous":
            self.pending_clarifications.append({
                "query": resolved.get("query") or raw,
                "raw": resolved.get("raw") or raw,
                "requested_quantity": resolved.get("requested_quantity"),
                "requested_unit": resolved.get("requested_unit"),
                "pack_size_filter": resolved.get("pack_size_filter"),
                "candidates": resolved.get("candidates") or [],
                "mention": resolved,
            })
            return

        if status != "resolved" or not resolved.get("resolved"):
            return

        line = resolved["resolved"]
        if resolved.get("in_stock") is False:
            self.pending_substitutions.append({
                "sku": line["sku"],
                "item": line["item"],
                "quantity": line["quantity"],
                "unit": line["unit"],
                "available": resolved.get("available"),
                "substitutes": resolved.get("substitutes") or [],
            })
            return

        self._upsert_cart(line, replace=(action == "set_quantity"))

    def _upsert_cart(self, resolved, replace=False):
        line = _cart_line(resolved)
        for existing in self.cart:
            if existing["sku"] == line["sku"]:
                if replace:
                    existing["quantity"] = line["quantity"]
                else:
                    existing["quantity"] = existing["quantity"] + line["quantity"]
                existing["line_total"] = existing["price"] * existing["quantity"]
                existing["unit"] = line["unit"]
                self.bill_shown = False
                return
        self.cart.append(line)
        self.bill_shown = False

    def _matching_cart_indexes(self, description):
        mention = resolver.resolve_mention(description)
        indexes = []
        candidate_skus = set()
        if mention.get("status") == "resolved" and mention.get("resolved"):
            candidate_skus.add(mention["resolved"]["sku"])
        for candidate in mention.get("candidates") or []:
            candidate_skus.add(candidate["sku"])
        for index, line in enumerate(self.cart):
            if line["sku"] in candidate_skus:
                indexes.append(index)
                continue
            item_l = line["item"].lower()
            desc_l = description.lower()
            if desc_l and desc_l in item_l:
                indexes.append(index)
        return indexes, mention

    def _remove_description(self, description):
        indexes, mention = self._matching_cart_indexes(description)
        for index in reversed(indexes):
            del self.cart[index]
            self.bill_shown = False

        remaining = []
        for pending in self.pending_clarifications:
            if mention.get("status") == "ambiguous":
                pending_skus = {item["sku"] for item in pending["candidates"]}
                mention_skus = {item["sku"] for item in mention.get("candidates") or []}
                if pending_skus & mention_skus:
                    continue
            if description.lower() in (pending.get("query") or "").lower():
                continue
            remaining.append(pending)
        self.pending_clarifications = remaining

        self.pending_substitutions = [
            item
            for item in self.pending_substitutions
            if description.lower() not in item["item"].lower()
        ]
        if indexes:
            self.last_notes.append("Removed " + description + ".")

    def _set_quantity(self, mention):
        description = mention["description"]
        indexes, resolved = self._matching_cart_indexes(description)
        if indexes:
            target = self.cart[indexes[0]]
            clause = _mention_clause(mention)
            updated = resolver.resolve_mention(clause)
            if updated.get("status") == "resolved" and updated.get("resolved"):
                if updated["resolved"]["sku"] == target["sku"] or updated["resolved"]["sku"] in {
                    self.cart[i]["sku"] for i in indexes
                }:
                    chosen = updated["resolved"]
                    if chosen["sku"] != target["sku"]:
                        # Keep the already chosen variety; reuse its SKU with new qty.
                        qty_line = resolver.resolve_mention(
                            str(mention.get("quantity"))
                            + " "
                            + (mention.get("unit") or "")
                            + " "
                            + target["item"]
                        )
                        if qty_line.get("resolved"):
                            chosen = qty_line["resolved"]
                            chosen["sku"] = target["sku"]
                            chosen["item"] = target["item"]
                            chosen["unit"] = target["unit"]
                    if updated.get("in_stock") is False and chosen["sku"] != target["sku"]:
                        self._ingest_resolved(updated, action="set_quantity")
                        return
                    target["quantity"] = chosen["quantity"]
                    product = order_engine.get_product(target["sku"])
                    target["price"] = product["price"]
                    target["unit"] = product["unit"]
                    target["line_total"] = product["price"] * target["quantity"]
                    self.bill_shown = False
                    return
            quantity = mention.get("quantity")
            if quantity is not None:
                target["quantity"] = quantity
                target["line_total"] = target["price"] * target["quantity"]
                self.bill_shown = False
            return

        for pending in self.pending_clarifications:
            pending_skus = {item["sku"] for item in pending["candidates"]}
            resolved_skus = {item["sku"] for item in resolved.get("candidates") or []}
            if pending.get("query") == resolved.get("query") or pending_skus & resolved_skus:
                pending["requested_quantity"] = mention.get("quantity")
                pending["requested_unit"] = mention.get("unit")
                pending["mention"]["requested_quantity"] = mention.get("quantity")
                pending["mention"]["requested_unit"] = mention.get("unit")
                for candidate in pending["candidates"]:
                    refreshed = resolver.resolve_mention(
                        _mention_clause({
                            "description": pending["query"],
                            "quantity": mention.get("quantity"),
                            "unit": mention.get("unit"),
                        }),
                        sku_whitelist=[candidate["sku"]],
                    )
                    if refreshed.get("candidates"):
                        candidate["quantity"] = refreshed["candidates"][0]["quantity"]
                return

        self._add_description(mention, action="set_quantity")

    def _handle_follow_up(self, intent, parsed, text):
        if intent == "reject_substitution":
            if self.pending_substitutions:
                skipped = self.pending_substitutions.pop(0)
                self.last_notes.append(
                    "Okay, I will skip " + skipped["item"] + "."
                )
            return self._compose_reply()

        selection = (
            parsed.get("accepted_substitute")
            or parsed.get("clarification_text")
            or text
        )
        if parsed.get("mentions"):
            selection = parsed["mentions"][0]["description"]

        if intent == "accept_substitution" or self.pending_substitutions:
            if self._try_accept_substitution(selection):
                return self._compose_reply()

        if self.pending_clarifications:
            self._apply_clarification_text(selection)
        return self._compose_reply()

    def _try_accept_substitution(self, selection):
        if not self.pending_substitutions:
            return False
        pending = self.pending_substitutions[0]
        whitelist = [option["sku"] for option in pending["substitutes"]]
        if not whitelist:
            return False
        resolved = resolver.resolve_mention(
            str(pending["quantity"]) + " " + selection,
            sku_whitelist=whitelist,
        )
        if resolved.get("status") != "resolved" or not resolved.get("resolved"):
            resolved = resolver.resolve_mention(selection, sku_whitelist=whitelist)
            if resolved.get("status") == "resolved" and resolved.get("resolved"):
                resolved["resolved"]["quantity"] = pending["quantity"]
        if resolved.get("status") != "resolved" or not resolved.get("resolved"):
            return False
        if resolved.get("in_stock") is False:
            self.last_notes.append(
                resolved["resolved"]["item"] + " does not have enough stock either."
            )
            return True
        self.pending_substitutions.pop(0)
        self._upsert_cart(resolved["resolved"], replace=True)
        self.last_notes.append("Added " + resolved["resolved"]["item"] + " instead.")
        return True

    def _apply_clarification_text(self, selection):
        if not self.pending_clarifications:
            return
        pending = self.pending_clarifications[0]
        updated = resolver.apply_clarification(pending["mention"], selection)
        if updated.get("status") != "resolved":
            self.last_notes.append(
                "Please choose one of: "
                + ", ".join(item["item"] for item in pending["candidates"])
                + "."
            )
            return
        self.pending_clarifications.pop(0)
        self._ingest_resolved(updated, action="set_quantity")

    def _load_usual_order(self):
        self.cart = []
        self.pending_clarifications = []
        self.pending_substitutions = []
        self.unsupported = []
        for mention in resolver.parse_usual_order(self.customer_id):
            self._ingest_resolved(mention, action="set_quantity")
        return self._compose_reply()

    def _cart_items(self):
        return [
            {"sku": line["sku"], "quantity": line["quantity"]}
            for line in self.cart
        ]

    def _preview(self):
        if not self.cart:
            return None
        return order_engine.prepare_order(self.customer_id, self._cart_items())

    def _ready_for_bill(self):
        return bool(
            self.cart
            and not self.pending_clarifications
            and not self.pending_substitutions
        )

    def _compose_reply(self):
        parts = list(self.last_notes)

        if self.cart and (
            self.pending_clarifications or self.pending_substitutions or self.unsupported
        ):
            added = ", ".join(
                str(line["quantity"]) + " " + line["unit"] + " " + line["item"]
                for line in self.cart
            )
            parts.append("Added: " + added + ".")

        for item in self.pending_substitutions:
            if item["available"] == 0:
                stock_text = item["item"] + " is out of stock."
            else:
                stock_text = (
                    item["item"]
                    + " has only "
                    + str(item["available"])
                    + " left; you asked for "
                    + str(item["quantity"])
                    + "."
                )
            names = [option["item"] for option in item["substitutes"] if option["stock"] > 0]
            if names:
                parts.append(
                    stock_text
                    + " Approved substitutes: "
                    + " or ".join(names)
                    + ". Should I use one of these?"
                )
            else:
                parts.append(stock_text + " There is no approved substitute.")

        for pending in self.pending_clarifications:
            options = ", ".join(item["item"] for item in pending["candidates"])
            qty = pending.get("requested_quantity")
            unit = pending.get("requested_unit") or ""
            label = (str(qty) + " " + unit + " " if qty is not None else "") + (
                pending.get("query") or "item"
            )
            parts.append(
                "Which "
                + label.strip()
                + " would you like: "
                + options
                + "?"
            )

        if self._ready_for_bill():
            preview = self._preview()
            self.bill_shown = True
            self.status = "awaiting_customer_confirmation"
            lines = []
            for line in self.cart:
                lines.append(
                    str(line["quantity"])
                    + " "
                    + line["unit"]
                    + " "
                    + line["item"]
                    + " @ "
                    + _rupees(line["price"])
                    + " = "
                    + _rupees(line["line_total"])
                )
            parts.append("Bill: " + "; ".join(lines) + ".")
            parts.append("Total " + _rupees(preview["total"]) + ".")
            if preview["approval"]["approval_required"]:
                parts.append(
                    "If you confirm, this will go to Ramesh for approval ("
                    + "; ".join(preview["approval"]["reasons"])
                    + ")."
                )
            parts.append("Please confirm if I should place this order.")
        elif self.cart and not parts:
            parts.append("Tell me if you want to add anything else, or confirm.")
        elif not parts:
            parts.append("What should I add to the order?")

        if self.pending_clarifications:
            self.status = "clarifying"
        elif self.pending_substitutions:
            self.status = "substituting"
        elif not self.cart and self.unsupported:
            self.status = "collecting"

        return " ".join(parts)

    def _confirm(self):
        if self.status in ("confirmed", "awaiting_owner_approval") and self.order_id:
            existing = order_engine.get_order(self.order_id)
            if existing is not None:
                return self._placed_reply(existing)

        if self.pending_clarifications or self.pending_substitutions:
            self.last_notes.append(
                "I still need an answer before I can place the order."
            )
            return self._compose_reply()

        if not self.cart:
            return "There are no items to confirm."

        preview = self._preview()
        if preview["shortages"]:
            for shortage in preview["shortages"]:
                product = order_engine.get_product(shortage["sku"])
                faux = {
                    "status": "resolved",
                    "resolved": {
                        "sku": shortage["sku"],
                        "quantity": shortage["requested"],
                        "unit": product["unit"],
                        "item": product["item"],
                    },
                    "in_stock": False,
                    "available": shortage["available"],
                    "substitutes": resolver.approved_substitutes(shortage["sku"]),
                }
                self._ingest_resolved(faux)
            self.last_notes.append("I cannot place it until stock is sorted.")
            return self._compose_reply()

        result = order_engine.confirm_order(
            self.customer_id,
            self._cart_items(),
            order_id=self.order_id,
        )
        if result.get("status") == "stock_issue":
            self.last_notes.append("Stock changed while placing the order.")
            return self._compose_reply()

        self.order_id = result["order_id"]
        self.status = result["status"]
        return self._placed_reply(result)

    def _placed_reply(self, order):
        if order["status"] == "awaiting_owner_approval":
            self.status = "awaiting_owner_approval"
            reasons = "; ".join(order.get("approval_reasons") or [])
            recommendation = order.get("agent_recommendation") or ""
            return (
                "I have sent this "
                + _rupees(order["total"])
                + " order to Ramesh for approval ("
                + reasons
                + "). It is not confirmed yet. "
                + recommendation
            ).strip()
        if order["status"] == "confirmed":
            self.status = "confirmed"
            return (
                "Order "
                + order["order_id"]
                + " is confirmed. Total "
                + _rupees(order["total"])
                + "."
            )
        return "Order status is " + str(order.get("status")) + "."

    def _cancel(self):
        if self.order_id:
            order = order_engine.get_order(self.order_id)
            if order and order["status"] in {
                "awaiting_owner_approval",
                "stock_issue",
                "awaiting_customer_confirmation",
            }:
                order_engine.cancel_order(self.order_id)
        self._reset_draft(status="cancelled")
        return "Cancelled. Nothing has been billed or reserved."

    def _snapshot(self, reply):
        preview = self._preview() if self.cart else None
        bill = None
        if preview is not None:
            bill = {
                "lines": [dict(line) for line in self.cart],
                "total": preview["total"],
                "approval_required": preview["approval"]["approval_required"],
                "approval_reasons": list(preview["approval"]["reasons"]),
                "agent_recommendation": preview.get("agent_recommendation"),
            }
        return {
            "ok": True,
            "customer_id": self.customer_id,
            "session_id": self.session_id,
            "reply": reply,
            "cart": [dict(line) for line in self.cart],
            "pending_questions": [
                {
                    "query": item["query"],
                    "candidates": [candidate["sku"] for candidate in item["candidates"]],
                    "options": [candidate["item"] for candidate in item["candidates"]],
                }
                for item in self.pending_clarifications
            ],
            "pending_substitutions": [
                {
                    "sku": item["sku"],
                    "item": item["item"],
                    "substitutes": [option["sku"] for option in item["substitutes"]],
                }
                for item in self.pending_substitutions
            ],
            "unsupported": list(self.unsupported),
            "bill": bill,
            "status": self.status,
            "order_id": self.order_id,
            "asked_clarification": bool(self.pending_clarifications),
        }
