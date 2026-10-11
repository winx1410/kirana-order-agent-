"""Gemini Flash NLU for messy kirana messages.

The model only extracts intent and raw product descriptions.
SKU matching, prices, stock and credit stay in resolver.py / order_engine.py.
"""

import json
import os
import re
from pathlib import Path


INTENTS = (
    "new_order",
    "add_items",
    "modify",
    "remove",
    "usual_order",
    "clarification",
    "confirm",
    "cancel",
    "accept_substitution",
    "reject_substitution",
)

MENTION_ACTIONS = ("add", "set_quantity", "remove")

UNIT_NORMALIZE = {
    "kilo": "kg",
    "kilos": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "kg": "kg",
    "litre": "L",
    "liter": "L",
    "litres": "L",
    "liters": "L",
    "ltr": "L",
    "l": "L",
    "pack": "pack",
    "packs": "pack",
    "pkt": "pack",
    "packet": "pack",
    "packets": "pack",
    "pouch": "pouch",
    "pouches": "pouch",
    "bottle": "bottle",
    "bottles": "bottle",
    "jar": "jar",
    "jars": "jar",
    "g": "g",
    "gm": "g",
    "gram": "g",
    "grams": "g",
    "ml": "ml",
}

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_DAILY_LIMIT = 200
SKU_RE = re.compile(r"^SKU-\d+$", re.I)

SYSTEM_INSTRUCTION = """You extract grocery-order structure for a neighbourhood kirana shop.
Return JSON only. Never invent a SKU, price, brand or product the customer did not mention.
Keep product descriptions in the customer's words (chini, tel, rice, Parle-G, Fortune oil).
Do not decide which catalogue item matches; another program does that.
Intents: new_order, add_items, modify, remove, usual_order, clarification, confirm, cancel, accept_substitution, reject_substitution.
Mention actions: add, set_quantity, remove.
Normalize units when obvious: kilo->kg, litre->L. Quantity must be a number or null.
If the customer answers a pending question, intent is clarification and clarification_text is their answer.
'haan/yes/confirm/ok confirm' is confirm. 'usual order/mera usual/bhejo usual' is usual_order.
A message may both change a quantity and remove an item; use intent modify and set each mention's action.
"""

RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": list(INTENTS)},
        "mentions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                    "unit": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "action": {"type": "string", "enum": list(MENTION_ACTIONS)},
                },
                "required": ["description", "action"],
            },
        },
        "clarification_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "accepted_substitute": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
    "required": ["intent", "mentions"],
}

_usage = {"calls": 0}


def reset_usage():
    _usage["calls"] = 0


def usage_count():
    return _usage["calls"]


def daily_limit():
    raw = os.environ.get("GEMINI_DAILY_LIMIT", str(DEFAULT_DAILY_LIMIT))
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_DAILY_LIMIT


def model_name():
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)


def _load_dotenv():
    """Copy unset keys from a local .env. Never overrides a real environment variable."""
    for path in (Path.cwd() / ".env", Path(__file__).resolve().parent / ".env"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _error_result(code, detail=None):
    return {
        "ok": False,
        "error": code,
        "detail": detail,
        "intent": None,
        "mentions": [],
        "clarification_text": None,
        "accepted_substitute": None,
        "raw": None,
    }


def _ok_result(payload):
    return {
        "ok": True,
        "error": None,
        "detail": None,
        "intent": payload["intent"],
        "mentions": payload["mentions"],
        "clarification_text": payload.get("clarification_text"),
        "accepted_substitute": payload.get("accepted_substitute"),
        "raw": payload,
    }


def extract_json_text(text):
    if text is None:
        return None
    stripped = str(text).strip()
    if not stripped:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.S)
    if fenced:
        return fenced.group(1)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start:end + 1]
    return stripped


def _normalize_unit(unit):
    if unit is None or unit == "":
        return None
    if not isinstance(unit, str):
        raise ValueError("invalid_unit")
    key = unit.strip().lower()
    if not key:
        return None
    return UNIT_NORMALIZE.get(key, unit.strip())


def _normalize_quantity(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("invalid_quantity")
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError("invalid_quantity")
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    if isinstance(value, str):
        stripped = value.strip().replace(",", "")
        if not re.fullmatch(r"\d+(?:\.\d+)?", stripped):
            raise ValueError("invalid_quantity")
        number = float(stripped)
        if number.is_integer():
            return int(number)
        return number
    raise ValueError("invalid_quantity")


def validate_payload(data):
    if not isinstance(data, dict):
        raise ValueError("invalid_json")

    intent = data.get("intent")
    if intent not in INTENTS:
        raise ValueError("invalid_intent")

    mentions_in = data.get("mentions")
    if mentions_in is None:
        mentions_in = []
    if not isinstance(mentions_in, list):
        raise ValueError("invalid_mentions")

    mentions = []
    for item in mentions_in:
        if not isinstance(item, dict):
            raise ValueError("invalid_mentions")
        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("invalid_description")
        description = description.strip()
        if SKU_RE.match(description) or "sku" in item:
            # Drop invented identifiers; keep only customer language.
            item = dict(item)
            item.pop("sku", None)
            if SKU_RE.match(description):
                raise ValueError("invented_sku")
        action = item.get("action") or "add"
        if action not in MENTION_ACTIONS:
            raise ValueError("invalid_action")
        mentions.append({
            "description": description,
            "quantity": _normalize_quantity(item.get("quantity")),
            "unit": _normalize_unit(item.get("unit")),
            "action": action,
        })

    clarification = data.get("clarification_text")
    if clarification is not None and not isinstance(clarification, str):
        raise ValueError("invalid_clarification")

    accepted = data.get("accepted_substitute")
    if accepted is not None and not isinstance(accepted, str):
        raise ValueError("invalid_substitute")

    return {
        "intent": intent,
        "mentions": mentions,
        "clarification_text": clarification,
        "accepted_substitute": accepted,
    }


def parse_model_text(text):
    blob = extract_json_text(text)
    if not blob:
        raise ValueError("invalid_json")
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc
    return validate_payload(data)


def _compact_context(context):
    if not context:
        return "none"
    parts = []
    cart = context.get("cart") or []
    if cart:
        lines = []
        for line in cart[:12]:
            desc = line.get("description") or line.get("item") or line.get("raw") or ""
            qty = line.get("quantity", "")
            unit = line.get("unit") or ""
            lines.append(f"{qty} {unit} {desc}".strip())
        parts.append("cart: " + "; ".join(lines))
    pending = context.get("pending_clarifications") or []
    if pending:
        bits = []
        for item in pending[:6]:
            query = item.get("query") or item.get("raw") or "item"
            options = item.get("options") or []
            bits.append(query + " -> " + ", ".join(str(opt) for opt in options[:6]))
        parts.append("pending_clarifications: " + " | ".join(bits))
    sub = context.get("pending_substitution")
    if sub:
        options = ", ".join(str(opt) for opt in (sub.get("options") or [])[:6])
        parts.append(
            "pending_substitution: "
            + str(sub.get("item") or "")
            + " options "
            + options
        )
    messages = context.get("recent_messages") or []
    if messages:
        clipped = []
        for message in messages[-4:]:
            role = message.get("role") or "user"
            text = (message.get("text") or "")[:160]
            clipped.append(role + ": " + text)
        parts.append("recent: " + " / ".join(clipped))
    return " | ".join(parts) if parts else "none"


def build_prompt(message, context=None):
    return (
        "Customer message:\n"
        + str(message).strip()
        + "\n\nConversation context:\n"
        + _compact_context(context)
    )


def _classify_api_error(exc):
    status = getattr(exc, "status", None)
    raw_code = getattr(exc, "code", None)
    text = (getattr(exc, "message", None) or str(exc)).lower()
    code = None
    for candidate in (raw_code, status):
        try:
            if candidate is not None:
                code = int(candidate)
                break
        except (TypeError, ValueError):
            if isinstance(candidate, str):
                text = candidate.lower() + " " + text

    if code == 429 or "quota" in text or "resource_exhausted" in text:
        return "quota_exhausted"
    if code in (404, 503) or "not found" in text or "unavailable" in text:
        return "model_unavailable"
    if code in (401, 403) or "api key" in text or "permission" in text:
        return "api_error"
    return "api_error"


def _call_gemini(prompt, client=None):
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError, ClientError, ServerError

    if client is None:
        _load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("missing_api_key")
        client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0,
        max_output_tokens=512,
        response_mime_type="application/json",
        response_json_schema=RESPONSE_JSON_SCHEMA,
    )
    try:
        response = client.models.generate_content(
            model=model_name(),
            contents=prompt,
            config=config,
        )
    except (ClientError, ServerError, APIError) as exc:
        raise RuntimeError(_classify_api_error(exc)) from exc
    except Exception as exc:
        raise RuntimeError(_classify_api_error(exc)) from exc

    text = getattr(response, "text", None)
    if not text and getattr(response, "candidates", None):
        try:
            text = response.candidates[0].content.parts[0].text
        except (AttributeError, IndexError):
            text = None
    return text


def interpret(message, context=None, client=None, generate=None):
    """Turn a customer utterance into validated intent JSON. Never calls the resolver."""
    if message is None or not str(message).strip():
        return _error_result("empty_message")

    if _usage["calls"] >= daily_limit():
        return _error_result("quota_exhausted", "local usage cap reached")

    prompt = build_prompt(message, context)
    _usage["calls"] += 1

    try:
        if generate is not None:
            raw_text = generate(prompt)
        else:
            raw_text = _call_gemini(prompt, client=client)
        payload = parse_model_text(raw_text)
    except ValueError as exc:
        return _error_result(str(exc) or "invalid_json")
    except RuntimeError as exc:
        code = str(exc) if str(exc) in {
            "quota_exhausted",
            "model_unavailable",
            "api_error",
            "missing_api_key",
        } else "api_error"
        return _error_result(code)

    return _ok_result(payload)
