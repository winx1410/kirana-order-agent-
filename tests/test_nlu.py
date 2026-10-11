import json
import os

import pytest

import nlu


@pytest.fixture(autouse=True)
def reset_nlu_usage():
    nlu.reset_usage()
    yield
    nlu.reset_usage()


class FakeResponse:
    def __init__(self, payload):
        if isinstance(payload, str):
            self.text = payload
        else:
            self.text = json.dumps(payload)


class FakeModels:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return FakeResponse(self.payload)


class FakeClient:
    def __init__(self, payload=None, error=None):
        self.models = FakeModels(payload=payload, error=error)


CLEAN_ORDER = {
    "intent": "new_order",
    "mentions": [
        {
            "description": "Fortune oil",
            "quantity": 1,
            "unit": "L",
            "action": "add",
        },
        {
            "description": "Parle-G",
            "quantity": 5,
            "unit": "pack",
            "action": "add",
        },
    ],
    "clarification_text": None,
    "accepted_substitute": None,
}

AMBIGUOUS_RICE = {
    "intent": "new_order",
    "mentions": [
        {
            "description": "sugar",
            "quantity": 2,
            "unit": "kg",
            "action": "add",
        },
        {
            "description": "rice",
            "quantity": 5,
            "unit": "kg",
            "action": "add",
        },
    ],
}

CHINI_TEL = {
    "intent": "new_order",
    "mentions": [
        {
            "description": "chini",
            "quantity": 2,
            "unit": "kilo",
            "action": "add",
        },
        {
            "description": "tel",
            "quantity": 1,
            "unit": "litre",
            "action": "add",
        },
    ],
}

PANEER_LAYS = {
    "intent": "new_order",
    "mentions": [
        {
            "description": "paneer",
            "quantity": 1,
            "unit": "kg",
            "action": "add",
        },
        {
            "description": "Lay's",
            "quantity": 2,
            "unit": None,
            "action": "add",
        },
    ],
}

MODIFY_CANCEL = {
    "intent": "modify",
    "mentions": [
        {
            "description": "rice",
            "quantity": 10,
            "unit": "kg",
            "action": "set_quantity",
        },
        {
            "description": "biscuits",
            "quantity": None,
            "unit": None,
            "action": "remove",
        },
    ],
}


def test_clean_order_extracts_fortune_oil_and_parle_g():
    result = nlu.interpret(
        "1 litre Fortune oil and 5 Parle-G",
        client=FakeClient(CLEAN_ORDER),
    )

    assert result["ok"] is True
    assert result["intent"] == "new_order"
    assert result["mentions"][0]["description"] == "Fortune oil"
    assert result["mentions"][0]["quantity"] == 1
    assert result["mentions"][0]["unit"] == "L"
    assert result["mentions"][1]["description"] == "Parle-G"
    assert result["mentions"][1]["quantity"] == 5
    assert "sku" not in result["mentions"][0]


def test_mixed_hindi_extracts_sugar_and_rice_without_picking_a_rice_sku():
    result = nlu.interpret(
        "bhaiya 2 kg sugar, 5 kg rice send kar do",
        client=FakeClient(AMBIGUOUS_RICE),
    )

    assert result["ok"] is True
    descriptions = [item["description"] for item in result["mentions"]]
    assert descriptions == ["sugar", "rice"]
    assert all("SKU-" not in item["description"] for item in result["mentions"])


def test_chini_and_tel_do_not_assume_an_oil_brand():
    result = nlu.interpret(
        "chini 2 kilo aur tel ek litre",
        client=FakeClient(CHINI_TEL),
    )

    assert result["ok"] is True
    assert result["mentions"][0]["description"] == "chini"
    assert result["mentions"][0]["unit"] == "kg"
    assert result["mentions"][1]["description"] == "tel"
    assert result["mentions"][1]["unit"] == "L"
    oil_text = result["mentions"][1]["description"].lower()
    assert "fortune" not in oil_text
    assert "saffola" not in oil_text


def test_paneer_and_lays_are_both_extracted():
    result = nlu.interpret(
        "1 kg paneer aur 2 Lay's",
        client=FakeClient(PANEER_LAYS),
    )

    assert result["ok"] is True
    assert result["mentions"][0]["description"].lower() == "paneer"
    assert result["mentions"][1]["description"] == "Lay's"


def test_usual_order_intent():
    payload = {
        "intent": "usual_order",
        "mentions": [],
        "clarification_text": None,
    }
    result = nlu.interpret("usual order bhejo", client=FakeClient(payload))
    assert result["ok"] is True
    assert result["intent"] == "usual_order"
    assert result["mentions"] == []


def test_modification_and_removal_in_one_message():
    result = nlu.interpret(
        "rice 10 kg kar do, biscuits cancel",
        context={
            "cart": [
                {"description": "rice", "quantity": 5, "unit": "kg"},
                {"description": "Parle-G", "quantity": 2, "unit": "pack"},
            ]
        },
        client=FakeClient(MODIFY_CANCEL),
    )

    assert result["ok"] is True
    assert result["intent"] == "modify"
    assert result["mentions"][0]["action"] == "set_quantity"
    assert result["mentions"][0]["quantity"] == 10
    assert result["mentions"][1]["action"] == "remove"
    assert result["mentions"][1]["description"] == "biscuits"


def test_explicit_confirmation():
    payload = {"intent": "confirm", "mentions": []}
    result = nlu.interpret("haan, confirm", client=FakeClient(payload))
    assert result["ok"] is True
    assert result["intent"] == "confirm"


def test_clarification_uses_conversation_context():
    payload = {
        "intent": "clarification",
        "mentions": [],
        "clarification_text": "Sona Masoori",
    }
    result = nlu.interpret(
        "Sona Masoori",
        context={
            "pending_clarifications": [{
                "query": "rice",
                "options": ["Sona Masoori", "Boiled Rice", "Basmati"],
            }]
        },
        client=FakeClient(payload),
    )
    assert result["intent"] == "clarification"
    assert result["clarification_text"] == "Sona Masoori"


def test_invalid_json_is_handled():
    result = nlu.interpret("hello", client=FakeClient("not json at all"))
    assert result["ok"] is False
    assert result["error"] == "invalid_json"
    assert result["mentions"] == []


def test_invalid_intent_is_handled():
    result = nlu.interpret(
        "hello",
        client=FakeClient({"intent": "hack_the_bill", "mentions": []}),
    )
    assert result["ok"] is False
    assert result["error"] == "invalid_intent"


def test_malformed_quantity_is_handled():
    result = nlu.interpret(
        "sugar",
        client=FakeClient({
            "intent": "new_order",
            "mentions": [{
                "description": "sugar",
                "quantity": "two-ish",
                "unit": "kg",
                "action": "add",
            }],
        }),
    )
    assert result["ok"] is False
    assert result["error"] == "invalid_quantity"


def test_invented_sku_description_is_rejected():
    result = nlu.interpret(
        "sugar",
        client=FakeClient({
            "intent": "new_order",
            "mentions": [{
                "description": "SKU-001",
                "quantity": 1,
                "action": "add",
            }],
        }),
    )
    assert result["ok"] is False
    assert result["error"] == "invented_sku"


def test_api_failure_is_handled():
    from google.genai.errors import ServerError

    error = ServerError(503, {"error": {"message": "unavailable"}})
    result = nlu.interpret("sugar", client=FakeClient(error=error))
    assert result["ok"] is False
    assert result["error"] in {"model_unavailable", "api_error"}


def test_quota_error_is_handled():
    from google.genai.errors import ClientError

    error = ClientError(429, {"error": {"message": "RESOURCE_EXHAUSTED quota"}})
    result = nlu.interpret("sugar", client=FakeClient(error=error))
    assert result["ok"] is False
    assert result["error"] == "quota_exhausted"


def test_local_usage_cap_blocks_further_calls(monkeypatch):
    monkeypatch.setenv("GEMINI_DAILY_LIMIT", "1")
    first = nlu.interpret("haan, confirm", client=FakeClient({"intent": "confirm", "mentions": []}))
    second = nlu.interpret("haan, confirm", client=FakeClient({"intent": "confirm", "mentions": []}))
    assert first["ok"] is True
    assert second["ok"] is False
    assert second["error"] == "quota_exhausted"


def test_prompt_includes_context_and_stays_compact():
    prompt = nlu.build_prompt(
        "Sona Masoori",
        {
            "cart": [{"description": "sugar", "quantity": 2, "unit": "kg"}],
            "pending_clarifications": [{"query": "rice", "options": ["Sona Masoori"]}],
            "recent_messages": [{"role": "assistant", "text": "which rice?"}],
        },
    )
    assert "Sona Masoori" in prompt
    assert "pending_clarifications" in prompt
    assert "SKU-002" not in prompt


def test_fenced_json_is_accepted():
    payload = nlu.parse_model_text("```json\n" + json.dumps(CLEAN_ORDER) + "\n```")
    assert payload["intent"] == "new_order"
    assert payload["mentions"][1]["quantity"] == 5


@pytest.mark.skipif(
    os.environ.get("NLU_LIVE_TEST") != "1" or not os.environ.get("GEMINI_API_KEY"),
    reason="live Gemini smoke disabled",
)
def test_live_gemini_smoke_clean_order():
    result = nlu.interpret("1 litre Fortune oil and 5 Parle-G")
    assert result["ok"] is True
    descriptions = " ".join(item["description"].lower() for item in result["mentions"])
    assert "fortune" in descriptions or "oil" in descriptions
    assert "parle" in descriptions
