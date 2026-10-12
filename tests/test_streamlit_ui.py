import nlu
import order_engine
from agent import reset_sessions
from streamlit.testing.v1 import AppTest


CREDIT_ITEMS = [
    {"sku": "SKU-005", "quantity": 1},
    {"sku": "SKU-009", "quantity": 2},
    {"sku": "SKU-014", "quantity": 1},
    {"sku": "SKU-023", "quantity": 1},
]


def _visible(app):
    parts = []
    for name in (
        "markdown",
        "subheader",
        "header",
        "title",
        "info",
        "caption",
        "success",
        "warning",
        "text",
    ):
        for block in getattr(app, name, []):
            value = getattr(block, "value", None)
            if isinstance(value, str):
                parts.append(value)
    for block in app.chat_message:
        for item in block.markdown:
            parts.append(item.value)
    return " ".join(parts)


def _ok(payload):
    parsed = nlu.validate_payload(payload)
    return {
        "ok": True,
        "error": None,
        "intent": parsed["intent"],
        "mentions": parsed["mentions"],
        "clarification_text": parsed.get("clarification_text"),
        "accepted_substitute": parsed.get("accepted_substitute"),
    }


def test_chat_calls_nlu_only_for_a_new_message(monkeypatch):
    calls = []

    def interpret(message, context=None, **kwargs):
        calls.append(message)
        return _ok({
            "intent": "new_order",
            "mentions": [
                {"description": "Fortune oil", "quantity": 1, "unit": "L", "action": "add"},
                {"description": "Parle-G", "quantity": 5, "unit": "pack", "action": "add"},
            ],
        })

    reset_sessions()
    order_engine.reset_state()
    monkeypatch.setattr(nlu, "interpret", interpret)

    app = AppTest.from_file("app.py", default_timeout=20)
    app.run()
    assert calls == []
    assert len(app.selectbox[0].options) == 7

    app.chat_input[0].set_value("1 litre Fortune oil and 5 Parle-G").run()
    assert calls == ["1 litre Fortune oil and 5 Parle-G"]
    assert "185" in _visible(app)

    app.run()
    assert calls == ["1 litre Fortune oil and 5 Parle-G"]

    app.selectbox[0].set_value("C001").run()
    assert calls == ["1 litre Fortune oil and 5 Parle-G"]
    assert order_engine.get_product("SKU-014")["stock"] == 60


def test_owner_queue_approves_once_without_calling_nlu(monkeypatch):
    def interpret(*args, **kwargs):
        raise AssertionError("owner page must not call Gemini")

    monkeypatch.setattr(nlu, "interpret", interpret)
    order_engine.reset_state()
    pending = order_engine.confirm_order("C001", CREDIT_ITEMS)

    page = AppTest.from_file("pages/owner_queue.py", default_timeout=20)
    page.run()
    visible = _visible(page)
    assert pending["order_id"] in visible
    assert "Suresh Reddy" in visible
    assert "880" in visible
    assert "credit" in visible.lower()

    page.button(key="approve-" + pending["order_id"]).click().run()
    assert order_engine.get_product("SKU-005")["stock"] == 24
    assert order_engine.get_approval_queue() == []

    page.run()
    assert order_engine.get_product("SKU-005")["stock"] == 24
    confirmed = _visible(page)
    assert pending["order_id"] in confirmed
    assert "Aashirvaad" in confirmed


CREDIT_NLU = {
    "intent": "new_order",
    "mentions": [
        {"description": "Aashirvaad 5 kg atta", "quantity": 1, "action": "add"},
        {"description": "toor dal", "quantity": 2, "unit": "kg", "action": "add"},
        {"description": "Fortune oil", "quantity": 1, "unit": "L", "action": "add"},
        {"description": "Tata Tea Gold", "quantity": 1, "action": "add"},
    ],
}


def _queue_credit_order(monkeypatch):
    calls = []

    def interpret(message, context=None, **kwargs):
        calls.append(message)
        if len(calls) == 1:
            return _ok(CREDIT_NLU)
        return _ok({"intent": "confirm", "mentions": []})

    monkeypatch.setattr(nlu, "interpret", interpret)
    reset_sessions()
    order_engine.reset_state()
    app = AppTest.from_file("app.py", default_timeout=20)
    app.run()
    app.chat_input[0].set_value(
        "Aashirvaad 5 kg atta, 2 kg toor dal, 1 litre Fortune oil aur 1 Tata Tea Gold bhej do"
    ).run()
    app.chat_input[0].set_value("haan, confirm").run()
    return app, calls


def test_chat_shows_approval_without_another_gemini_call(monkeypatch):
    app, calls = _queue_credit_order(monkeypatch)
    assert "This order is with Ramesh. It is not confirmed yet." in _visible(app)
    before = len(calls)
    order_id = order_engine.get_approval_queue()[0]["order_id"]
    order_engine.review_order(order_id, approve=True)
    app.run()
    assert len(calls) == before
    visible = _visible(app)
    assert "Ramesh approved this order. It is confirmed." in visible
    assert "This order is with Ramesh. It is not confirmed yet." not in visible
    assert "Status: confirmed" in visible
    assert order_engine.get_product("SKU-005")["stock"] == 24


def test_chat_shows_rejection_without_another_gemini_call(monkeypatch):
    app, calls = _queue_credit_order(monkeypatch)
    before = len(calls)
    order_id = order_engine.get_approval_queue()[0]["order_id"]
    order_engine.review_order(order_id, approve=False)
    app.run()
    assert len(calls) == before
    visible = _visible(app)
    assert "Ramesh rejected this order. Nothing was reserved." in visible
    assert "This order is with Ramesh. It is not confirmed yet." not in visible
    assert "Status: rejected" in visible
    assert order_engine.get_product("SKU-005")["stock"] == 25
    assert order_engine.get_customer("C001")["outstanding"] == 4800


def test_rice_clarification_names_loose_kg_and_packs(monkeypatch):
    def interpret(message, context=None, **kwargs):
        return _ok({
            "intent": "new_order",
            "mentions": [
                {"description": "sugar", "quantity": 2, "unit": "kg", "action": "add"},
                {"description": "rice", "quantity": 5, "unit": "kg", "action": "add"},
            ],
        })

    monkeypatch.setattr(nlu, "interpret", interpret)
    reset_sessions()
    order_engine.reset_state()
    app = AppTest.from_file("app.py", default_timeout=20)
    app.run()
    app.selectbox[0].set_value("C002").run()
    app.chat_input[0].set_value("bhaiya 2 kg sugar, 5 kg rice send kar do").run()
    visible = _visible(app)
    assert "Loose, sold per kg" in visible
    assert "5 kg Sona Masoori Rice (loose)" in visible
    assert "5 kg Boiled Rice (loose)" in visible
    assert "5 packs of India Gate Basmati Rice, 1 kg" in visible
    assert "I have not chosen one." in visible
    assert order_engine.get_product("SKU-002")["stock"] == 150
