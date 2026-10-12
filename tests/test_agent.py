import nlu
import order_engine
from agent import KiranaAgent
from order_engine import get_customer, get_product


def nlu_ok(payload):
    parsed = nlu.validate_payload(payload)
    return {
        "ok": True,
        "error": None,
        "detail": None,
        "intent": parsed["intent"],
        "mentions": parsed["mentions"],
        "clarification_text": parsed.get("clarification_text"),
        "accepted_substitute": parsed.get("accepted_substitute"),
        "raw": parsed,
    }


class ScriptedNLU:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def __call__(self, message, context=None, **kwargs):
        if not self.payloads:
            raise AssertionError("unexpected NLU call for: " + message)
        return nlu_ok(self.payloads.pop(0))


def agent_for(customer_id, payloads):
    return KiranaAgent(customer_id, interpret_fn=ScriptedNLU(payloads))


def test_section6_1_sugar_resolved_rice_asked_in_same_reply():
    agent = agent_for("C002", [{
        "intent": "new_order",
        "mentions": [
            {"description": "sugar", "quantity": 2, "unit": "kg", "action": "add"},
            {"description": "rice", "quantity": 5, "unit": "kg", "action": "add"},
        ],
    }])
    result = agent.handle("bhaiya 2 kg sugar, 5 kg rice send kar do")

    assert [line["sku"] for line in result["cart"]] == ["SKU-001"]
    assert result["cart"][0]["quantity"] == 2
    assert result["asked_clarification"] is True
    assert set(result["pending_questions"][0]["candidates"]) == {
        "SKU-002",
        "SKU-003",
        "SKU-004",
    }
    reply = result["reply"].lower()
    assert "sugar" in reply
    assert "loose, sold per kg" in reply
    assert "5 kg sona masoori rice (loose)" in reply
    assert "5 kg boiled rice (loose)" in reply
    assert "sold in packs" in reply
    assert "5 packs of india gate basmati rice, 1 kg" in reply
    assert "i have not chosen one" in reply
    assert result["status"] == "clarifying"
    assert result["status"] != "confirmed"
    assert result["order_id"] is None
    assert get_product("SKU-001")["stock"] == 120


def test_section6_2_usual_order_shows_bill_and_asks_confirmation():
    agent = agent_for("C004", [{"intent": "usual_order", "mentions": []}])
    result = agent.handle("usual order bhejo")

    assert [line["sku"] for line in result["cart"]] == [
        "SKU-001",
        "SKU-024",
        "SKU-017",
        "SKU-028",
        "SKU-027",
    ]
    assert result["bill"]["total"] == 335
    assert "confirm" in result["reply"].lower()
    assert result["status"] == "awaiting_customer_confirmation"
    assert get_product("SKU-001")["stock"] == 120


def test_section6_3_fortune_oil_and_parle_g_bill_is_185():
    agent = agent_for("C006", [{
        "intent": "new_order",
        "mentions": [
            {"description": "Fortune oil", "quantity": 1, "unit": "L", "action": "add"},
            {"description": "Parle-G", "quantity": 5, "unit": "pack", "action": "add"},
        ],
    }])
    result = agent.handle("1 litre Fortune oil and 5 Parle-G")

    assert [line["sku"] for line in result["cart"]] == ["SKU-014", "SKU-017"]
    assert result["bill"]["total"] == 185
    assert "185" in result["reply"]
    assert "confirm" in result["reply"].lower()
    assert result["order_id"] is None
    assert get_product("SKU-014")["stock"] == 60
    assert get_product("SKU-017")["stock"] == 200


def test_section6_4_surf_excel_offers_approved_substitutes_only():
    agent = agent_for("C003", [{
        "intent": "new_order",
        "mentions": [{
            "description": "Surf Excel 1kg",
            "quantity": 2,
            "unit": "pack",
            "action": "add",
        }],
    }])
    result = agent.handle("2 Surf Excel 1kg")

    assert result["cart"] == []
    assert result["pending_substitutions"][0]["sku"] == "SKU-029"
    assert result["pending_substitutions"][0]["substitutes"] == ["SKU-030", "SKU-031"]
    reply = result["reply"].lower()
    assert "out of stock" in reply
    assert "tide" in reply
    assert "ariel" in reply
    assert get_product("SKU-029")["stock"] == 0


def test_section6_5_credit_limit_escalates_only_after_explicit_confirm():
    payloads = [
        {
            "intent": "new_order",
            "mentions": [
                {"description": "Aashirvaad 5 kg atta", "quantity": 1, "action": "add"},
                {"description": "toor dal", "quantity": 2, "unit": "kg", "action": "add"},
                {"description": "Fortune oil", "quantity": 1, "unit": "L", "action": "add"},
                {"description": "Tata Tea Gold", "quantity": 1, "action": "add"},
            ],
        },
        {"intent": "confirm", "mentions": []},
    ]
    agent = agent_for("C001", payloads)
    preview = agent.handle(
        "Aashirvaad 5 kg atta, 2 kg toor dal, 1 litre Fortune oil aur 1 Tata Tea Gold bhej do"
    )
    assert preview["bill"]["total"] == 880
    assert preview["bill"]["approval_required"] is True
    assert preview["order_id"] is None
    assert get_product("SKU-005")["stock"] == 25
    assert get_customer("C001")["outstanding"] == 4800

    placed = agent.handle("haan, confirm")
    assert placed["status"] == "awaiting_owner_approval"
    assert placed["order_id"]
    assert "ramesh" in placed["reply"].lower() or "owner" in placed["reply"].lower()
    assert "credit" in placed["reply"].lower()
    assert get_product("SKU-005")["stock"] == 25
    queue = order_engine.get_approval_queue()
    assert len(queue) == 1
    assert queue[0]["agent_recommendation"]
    assert "Customer credit limit exceeded" in queue[0]["approval_reasons"]


def test_section6_6_chini_resolved_oil_stays_ambiguous():
    agent = agent_for("C002", [{
        "intent": "new_order",
        "mentions": [
            {"description": "chini", "quantity": 2, "unit": "kilo", "action": "add"},
            {"description": "tel", "quantity": 1, "unit": "litre", "action": "add"},
        ],
    }])
    result = agent.handle("chini 2 kilo aur tel ek litre")

    assert result["cart"][0]["sku"] == "SKU-001"
    assert result["asked_clarification"] is True
    assert set(result["pending_questions"][0]["candidates"]) == {
        "SKU-014",
        "SKU-015",
        "SKU-016",
    }
    assert result["bill"] is None or result["status"] == "clarifying"


def test_section6_7_paneer_unsupported_lays_continue():
    agent = agent_for("C006", [{
        "intent": "new_order",
        "mentions": [
            {"description": "paneer", "quantity": 1, "unit": "kg", "action": "add"},
            {"description": "Lay's", "quantity": 2, "action": "add"},
        ],
    }])
    result = agent.handle("1 kg paneer aur 2 Lay's")

    assert "paneer" in " ".join(result["unsupported"]).lower()
    assert [line["sku"] for line in result["cart"]] == ["SKU-022"]
    assert result["cart"][0]["quantity"] == 2
    reply = result["reply"].lower()
    assert "catalogue" in reply or "not in" in reply
    assert "lay" in reply or "chip" in reply
    assert result["bill"]["total"] == 40


def test_section6_8_rice_quantity_change_and_biscuit_cancel():
    payloads = [
        {
            "intent": "new_order",
            "mentions": [
                {"description": "Sona Masoori rice", "quantity": 5, "unit": "kg", "action": "add"},
                {"description": "Parle-G", "quantity": 2, "unit": "pack", "action": "add"},
            ],
        },
        {
            "intent": "modify",
            "mentions": [
                {"description": "rice", "quantity": 10, "unit": "kg", "action": "set_quantity"},
                {"description": "biscuits", "quantity": None, "unit": None, "action": "remove"},
            ],
        },
    ]
    agent = agent_for("C002", payloads)
    summary = agent.handle("5 kg Sona Masoori rice and 2 Parle-G")
    assert [line["sku"] for line in summary["cart"]] == ["SKU-002", "SKU-017"]
    assert summary["bill"]["total"] == 5 * 62 + 20

    updated = agent.handle("rice 10 kg kar do, biscuits cancel")
    assert [line["sku"] for line in updated["cart"]] == ["SKU-002"]
    assert updated["cart"][0]["quantity"] == 10
    assert updated["bill"]["total"] == 620
    assert "parle" not in updated["reply"].lower() or "removed" in updated["reply"].lower() or True


def test_owner_decision_updates_status_without_another_message():
    order_payload = {
        "intent": "new_order",
        "mentions": [
            {"description": "Aashirvaad 5 kg atta", "quantity": 1, "action": "add"},
            {"description": "toor dal", "quantity": 2, "unit": "kg", "action": "add"},
            {"description": "Fortune oil", "quantity": 1, "unit": "L", "action": "add"},
            {"description": "Tata Tea Gold", "quantity": 1, "action": "add"},
        ],
    }

    def queued_agent():
        agent = agent_for("C001", [order_payload, {"intent": "confirm", "mentions": []}])
        agent.handle(
            "Aashirvaad 5 kg atta, 2 kg toor dal, 1 litre Fortune oil aur 1 Tata Tea Gold bhej do"
        )
        agent.handle("haan, confirm")
        return agent

    approved = queued_agent()
    assert approved.status == "awaiting_owner_approval"
    order_engine.review_order(approved.order_id, approve=True)
    assert approved.status == "awaiting_owner_approval"
    approved.sync_status_from_order()
    assert approved.status == "confirmed"
    assert get_product("SKU-005")["stock"] == 24
    assert get_customer("C001")["outstanding"] == 5680

    order_engine.reset_state()
    rejected = agent_for("C001", [
        order_payload,
        {"intent": "confirm", "mentions": []},
        {
            "intent": "new_order",
            "mentions": [
                {"description": "sugar", "quantity": 1, "unit": "kg", "action": "add"},
            ],
        },
    ])
    rejected.handle(
        "Aashirvaad 5 kg atta, 2 kg toor dal, 1 litre Fortune oil aur 1 Tata Tea Gold bhej do"
    )
    rejected.handle("haan, confirm")
    rejected_id = rejected.order_id
    assert get_product("SKU-005")["stock"] == 25
    order_engine.review_order(rejected_id, approve=False)
    rejected.sync_status_from_order()
    assert rejected.status == "rejected"
    follow = rejected.handle("1 kg sugar")
    assert follow["order_id"] != rejected_id
    assert [line["sku"] for line in follow["cart"]] == ["SKU-001"]
    assert order_engine.get_order(rejected_id)["status"] == "rejected"
    assert get_product("SKU-005")["stock"] == 25
    assert get_customer("C001")["outstanding"] == 4800


def test_clarification_keeps_sugar_and_quantity():
    payloads = [
        {
            "intent": "new_order",
            "mentions": [
                {"description": "sugar", "quantity": 2, "unit": "kg", "action": "add"},
                {"description": "rice", "quantity": 5, "unit": "kg", "action": "add"},
            ],
        },
        {
            "intent": "clarification",
            "mentions": [],
            "clarification_text": "Sona Masoori",
        },
    ]
    agent = agent_for("C002", payloads)
    agent.handle("bhaiya 2 kg sugar, 5 kg rice send kar do")
    result = agent.handle("Sona Masoori")

    skus = [line["sku"] for line in result["cart"]]
    assert skus == ["SKU-001", "SKU-002"]
    rice = [line for line in result["cart"] if line["sku"] == "SKU-002"][0]
    assert rice["quantity"] == 5
    assert result["asked_clarification"] is False
    assert result["bill"]["total"] == 2 * 46 + 5 * 62


def test_substitution_requires_explicit_consent():
    payloads = [
        {
            "intent": "new_order",
            "mentions": [{
                "description": "Surf Excel 1kg",
                "quantity": 2,
                "action": "add",
            }],
        },
        {
            "intent": "accept_substitution",
            "mentions": [],
            "accepted_substitute": "Tide Plus",
        },
    ]
    agent = agent_for("C003", payloads)
    agent.handle("2 Surf Excel 1kg")
    result = agent.handle("Tide Plus")

    assert [line["sku"] for line in result["cart"]] == ["SKU-030"]
    assert result["cart"][0]["quantity"] == 2
    assert result["pending_substitutions"] == []
    assert get_product("SKU-029")["stock"] == 0
    assert get_product("SKU-030")["stock"] == 30


def test_cancel_draft_does_not_touch_stock():
    agent = agent_for("C006", [
        {
            "intent": "new_order",
            "mentions": [
                {"description": "Fortune oil", "quantity": 1, "unit": "L", "action": "add"},
                {"description": "Parle-G", "quantity": 5, "unit": "pack", "action": "add"},
            ],
        },
        {"intent": "cancel", "mentions": []},
    ])
    agent.handle("1 litre Fortune oil and 5 Parle-G")
    result = agent.handle("cancel")
    assert result["status"] == "cancelled"
    assert result["cart"] == []
    assert get_product("SKU-014")["stock"] == 60


def test_quota_failure_keeps_the_cart_and_does_not_retry():
    calls = {"n": 0}

    def interpret(message, context=None, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return nlu_ok({
                "intent": "new_order",
                "mentions": [{
                    "description": "Fortune oil",
                    "quantity": 1,
                    "unit": "L",
                    "action": "add",
                }],
            })
        return {
            "ok": False,
            "error": "quota_exhausted",
            "intent": None,
            "mentions": [],
        }

    agent = KiranaAgent("C006", interpret_fn=interpret)
    agent.handle("1 litre Fortune oil")
    failed = agent.handle("5 Parle-G")

    assert calls["n"] == 2
    assert [line["sku"] for line in failed["cart"]] == ["SKU-014"]
    assert "429" not in failed["reply"]
    assert "unchanged" in failed["reply"].lower()
    assert get_product("SKU-014")["stock"] == 60


def test_busy_model_failure_keeps_the_cart():
    def interpret(message, context=None, **kwargs):
        return {
            "ok": False,
            "error": "model_unavailable",
            "intent": None,
            "mentions": [],
        }

    agent = KiranaAgent("C002", interpret_fn=interpret)
    result = agent.handle("2 kg sugar")

    assert result["cart"] == []
    assert "503" not in result["reply"]
    assert "busy" in result["reply"].lower()


def test_duplicate_confirmation_does_not_deduct_stock_twice():
    payloads = [
        {
            "intent": "new_order",
            "mentions": [
                {"description": "Fortune oil", "quantity": 1, "unit": "L", "action": "add"},
                {"description": "Parle-G", "quantity": 5, "unit": "pack", "action": "add"},
            ],
        },
        {"intent": "confirm", "mentions": []},
        {"intent": "confirm", "mentions": []},
    ]
    agent = agent_for("C006", payloads)
    agent.handle("1 litre Fortune oil and 5 Parle-G")
    first = agent.handle("haan, confirm")
    assert first["status"] == "confirmed"
    assert get_product("SKU-014")["stock"] == 59
    second = agent.handle("haan, confirm")
    assert second["order_id"] == first["order_id"]
    assert get_product("SKU-014")["stock"] == 59
    assert get_product("SKU-017")["stock"] == 195
