"""Mocked-NLU outcome evaluation. Does not call Gemini."""

import pytest

import order_engine
from agent import KiranaAgent, reset_sessions
from evals.scenarios import CASES
from nlu import validate_payload


def _scripted(payloads):
    pending = list(payloads)

    def interpret(message, context=None, **kwargs):
        if not pending:
            raise AssertionError("unexpected NLU call for: " + message)
        parsed = validate_payload(pending.pop(0))
        return {
            "ok": True,
            "error": None,
            "intent": parsed["intent"],
            "mentions": parsed["mentions"],
            "clarification_text": parsed.get("clarification_text"),
            "accepted_substitute": parsed.get("accepted_substitute"),
        }

    return interpret


def _cart(result):
    return [(line["sku"], line["quantity"]) for line in result["cart"]]


def _catalogue_total(lines):
    """Bill from catalogue unit price times quantity. Does not use calculate_total."""
    total = 0
    for sku, quantity in lines:
        product = order_engine.get_product(sku)
        total += product["price"] * quantity
    return total


def _check(expect, result, agent):
    if "cart" in expect:
        assert _cart(result) == expect["cart"]
    if "status" in expect:
        assert result["status"] == expect["status"]
    if "total" in expect:
        expected_total = expect["total"]
        if "cart" in expect:
            expected_total = _catalogue_total(expect["cart"])
            assert expect["total"] == expected_total
        assert result["bill"]["total"] == expected_total
    if "clarification" in expect:
        assert result["asked_clarification"] is expect["clarification"]
    if "clarification_skus" in expect:
        assert result["asked_clarification"] is True
        assert sorted(result["pending_questions"][0]["candidates"]) == sorted(
            expect["clarification_skus"]
        )
    if "substitutions" in expect:
        actual = [
            (item["sku"], item["substitutes"])
            for item in result["pending_substitutions"]
        ]
        assert actual == expect["substitutions"]
    if "unsupported_contains" in expect:
        assert expect["unsupported_contains"] in " ".join(result["unsupported"]).lower()
    if "approval_required" in expect:
        assert result["bill"]["approval_required"] is expect["approval_required"]
    if "approval_reasons" in expect:
        assert result["bill"]["approval_reasons"] == expect["approval_reasons"]
    if "order_status" in expect:
        order = order_engine.get_order(agent.order_id) if agent.order_id else None
        actual = order["status"] if order else None
        assert actual == expect["order_status"]
    if "queue_len" in expect:
        assert len(order_engine.get_approval_queue()) == expect["queue_len"]
    if "approval_reasons_on_queue" in expect:
        queue = order_engine.get_approval_queue()
        assert queue[0]["approval_reasons"] == expect["approval_reasons_on_queue"]
    if expect.get("recommendation_present"):
        assert order_engine.get_approval_queue()[0]["agent_recommendation"]
    if "outstanding" in expect:
        customer = order_engine.get_customer(agent.customer_id)
        assert customer["outstanding"] == expect["outstanding"]
    if "stocks" in expect:
        for sku, stock in expect["stocks"].items():
            assert order_engine.get_product(sku)["stock"] == stock
    if expect.get("same_order"):
        assert result["order_id"] == agent.order_id


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_evaluation_case(case):
    reset_sessions()
    order_engine.reset_state()
    nlu_turns = [turn["nlu"] for turn in case["turns"] if "nlu" in turn]
    agent = KiranaAgent(case["customer_id"], interpret_fn=_scripted(nlu_turns))
    first_order_id = None

    for turn in case["turns"]:
        if turn.get("action") == "owner_approve":
            order_engine.review_order(agent.order_id, approve=True)
            agent.sync_status_from_order()
            result = {
                "status": agent.status,
                "cart": agent.cart,
                "bill": None,
                "asked_clarification": False,
                "pending_questions": [],
                "pending_substitutions": [],
                "unsupported": [],
                "order_id": agent.order_id,
            }
        else:
            result = agent.handle(turn["message"])
            if first_order_id is None and result.get("order_id"):
                first_order_id = result["order_id"]
            if turn.get("expect", {}).get("same_order"):
                assert result["order_id"] == first_order_id
        _check(turn["expect"], result, agent)
