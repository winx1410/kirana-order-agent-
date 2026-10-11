import re

import order_engine


FILLER_PHRASES = (
    r"\bsend kar do\b",
    r"\bbhej do\b",
    r"\bkar do\b",
    r"\bbhejo\b",
    r"\bsend\b",
    r"\bplease\b",
    r"\bbhaiya\b",
    r"\bbhai\b",
)

USUAL_RE = re.compile(
    r"\b(usual order|the usual|mera usual|regular order|usual)\b",
    re.I,
)

HINDI_NUMBERS = {
    "ek": 1,
    "one": 1,
    "do": 2,
    "two": 2,
    "teen": 3,
    "tin": 3,
    "three": 3,
    "char": 4,
    "chaar": 4,
    "four": 4,
    "panch": 5,
    "paanch": 5,
    "five": 5,
    "che": 6,
    "chhe": 6,
    "six": 6,
    "saat": 7,
    "seven": 7,
    "aath": 8,
    "eight": 8,
    "nau": 9,
    "nine": 9,
    "das": 10,
    "ten": 10,
}

UNIT_ALIASES = {
    "kg": "kg",
    "kilo": "kg",
    "kilos": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "g": "g",
    "gm": "g",
    "gram": "g",
    "grams": "g",
    "l": "L",
    "ltr": "L",
    "litre": "L",
    "liter": "L",
    "litres": "L",
    "liters": "L",
    "ml": "ml",
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
}

STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "ka",
    "ki",
    "ke",
    "and",
    "with",
    "for",
    "some",
    "my",
    "mera",
    "meri",
}

PACK_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g|l|ml)\b", re.I)

UNIT_ALT = "|".join(
    sorted(UNIT_ALIASES.keys(), key=len, reverse=True)
)
HINDI_ALT = "|".join(
    sorted(HINDI_NUMBERS.keys(), key=len, reverse=True)
)
QTY_UNIT_RE = re.compile(
    r"(?:(?P<num>\d+(?:\.\d+)?)|\b(?P<hnum>"
    + HINDI_ALT
    + r")\b)(?:\s*(?P<unit>"
    + UNIT_ALT
    + r")\b)?",
    re.I,
)


def normalize_text(text):
    if text is None:
        return ""
    lowered = str(text).lower().replace("’", "'")
    lowered = lowered.replace("'", "")
    lowered = lowered.replace("-", " ")
    lowered = re.sub(r"[()/.,;!?]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def tokenize(text):
    return [
        token
        for token in normalize_text(text).split()
        if token and token not in STOPWORDS
    ]


def _contains_phrase(text, phrase):
    if not phrase:
        return False
    return re.search(r"\b" + re.escape(phrase) + r"\b", text) is not None


def _parse_pack_size(item_name):
    match = PACK_SIZE_RE.search(item_name or "")
    if not match:
        return None, None
    value = float(match.group(1))
    if value.is_integer():
        value = int(value)
    unit = match.group(2).lower()
    if unit == "l":
        unit = "L"
    return value, unit


def _convert_measure(value, from_unit, to_unit):
    if from_unit == to_unit:
        return value
    if from_unit == "g" and to_unit == "kg":
        return value / 1000.0
    if from_unit == "kg" and to_unit == "g":
        return value * 1000.0
    if from_unit == "ml" and to_unit == "L":
        return value / 1000.0
    if from_unit == "L" and to_unit == "ml":
        return value * 1000.0
    return None


def _catalogue_index():
    indexed = []
    document_frequency = {}

    for product in order_engine.catalogue:
        item_without_size = PACK_SIZE_RE.sub(" ", product["item"])
        aliases = [normalize_text(alias) for alias in product["also_called"]]
        tokens = set(tokenize(item_without_size))
        for alias in product["also_called"]:
            tokens.update(tokenize(alias))
        pack_size, pack_unit = _parse_pack_size(product["item"])
        is_loose = "(loose)" in product["item"].lower() or (
            product["unit"] == "kg" and pack_size is None
        )
        record = {
            "sku": product["sku"],
            "item": product["item"],
            "unit": product["unit"],
            "price": product["price"],
            "stock": product["stock"],
            "substitutes": list(product["substitutes"]),
            "aliases": aliases,
            "tokens": tokens,
            "pack_size": pack_size,
            "pack_unit": pack_unit,
            "is_loose": is_loose,
        }
        indexed.append(record)
        for token in tokens:
            document_frequency[token] = document_frequency.get(token, 0) + 1

    for record in indexed:
        record["rare"] = {
            token
            for token in record["tokens"]
            if document_frequency.get(token, 0) <= 2
        }

    return indexed


def split_clauses(text):
    cleaned = str(text)
    for phrase in FILLER_PHRASES:
        cleaned = re.sub(phrase, " ", cleaned, flags=re.I)
    parts = re.split(
        r"\s*(?:,+|/\s+|\baur\b|\band\b|\bplus\b|&)\s*",
        cleaned,
        flags=re.I,
    )
    return [part.strip() for part in parts if normalize_text(part)]


def _qty_from_match(match):
    if match.group("num"):
        value = float(match.group("num"))
        if value.is_integer():
            value = int(value)
    else:
        value = HINDI_NUMBERS[match.group("hnum").lower()]
    unit = match.group("unit")
    if unit:
        unit = UNIT_ALIASES[unit.lower()]
    return value, unit


def parse_clause(clause):
    """Pull quantity, unit and leftover product text from one clause."""
    text = normalize_text(clause)
    matches = list(QTY_UNIT_RE.finditer(text))
    useful = []
    for match in matches:
        value, unit = _qty_from_match(match)
        useful.append((match.start(), match.end(), value, unit))

    pack_size_filter = None
    quantity = None
    requested_unit = None
    query = text

    if len(useful) >= 2:
        quantity = useful[0][2]
        requested_unit = useful[0][3]
        pack_size_filter = (useful[1][2], useful[1][3])
        query = (text[: useful[0][0]] + " " + text[useful[0][1]: useful[1][0]] + " " + text[useful[1][1]:]).strip()
    elif len(useful) == 1:
        quantity = useful[0][2]
        requested_unit = useful[0][3]
        query = (text[: useful[0][0]] + " " + text[useful[0][1]:]).strip()

    query = re.sub(r"\s+", " ", query).strip()
    query_tokens = [
        token
        for token in tokenize(query)
        if token not in UNIT_ALIASES and token not in HINDI_NUMBERS
    ]
    query = " ".join(query_tokens)
    return {
        "raw": clause,
        "query": query,
        "requested_quantity": 1 if quantity is None else quantity,
        "quantity_was_implied": quantity is None,
        "requested_unit": requested_unit,
        "pack_size_filter": pack_size_filter,
    }


def _score_product(query, product):
    qn = normalize_text(query)
    if not qn:
        return 0

    q_tokens = set(tokenize(qn))
    score = 0

    item_norm = normalize_text(PACK_SIZE_RE.sub(" ", product["item"]))
    if qn == item_norm or _contains_phrase(item_norm, qn):
        score += 70

    for alias in product["aliases"]:
        if alias and _contains_phrase(qn, alias):
            score += 40 if len(alias) > 3 or alias == qn else 28

    overlap = q_tokens & product["tokens"]
    if not overlap and score == 0:
        return 0

    score += 8 * len(overlap)
    score += 22 * len(q_tokens & product["rare"])
    return score


def find_products(query, sku_whitelist=None):
    """Return catalogue products that match a product phrase. Never invent SKUs."""
    index = _catalogue_index()
    if sku_whitelist is not None:
        allowed = set(sku_whitelist)
        index = [product for product in index if product["sku"] in allowed]

    q_tokens = set(tokenize(query))
    scored = []
    for product in index:
        score = _score_product(query, product)
        if score > 0:
            scored.append((score, product))

    if not scored:
        return []

    scored.sort(key=lambda item: item[0], reverse=True)
    max_score = scored[0][0]
    query_rare = set()
    for _, product in scored:
        query_rare |= q_tokens & product["rare"]

    matches = []
    for score, product in scored:
        if query_rare and not (q_tokens & product["rare"]):
            continue
        if score >= max_score - 18 or score >= max_score * 0.55:
            matches.append(product)

    if not matches:
        matches = [product for score, product in scored if score >= max_score - 5]
    return matches


def _line_quantity(product, requested_quantity, requested_unit):
    quantity = 1 if requested_quantity is None else requested_quantity

    if product["is_loose"] or product["unit"] == "kg":
        if requested_unit in (None, "kg"):
            return quantity, "kg"
        converted = _convert_measure(quantity, requested_unit, "kg")
        if converted is None:
            return None, "kg"
        return converted, "kg"

    if requested_unit is None or requested_unit in {
        "pack",
        "pouch",
        "bottle",
        "jar",
        product["unit"],
    }:
        return quantity, product["unit"]

    if product["pack_size"] is None or product["pack_unit"] is None:
        return None, product["unit"]

    converted = _convert_measure(
        quantity, requested_unit, product["pack_unit"]
    )
    if converted is None:
        return None, product["unit"]
    packs = converted / product["pack_size"]
    return packs, product["unit"]


def _validated_candidate(product, requested_quantity, requested_unit, pack_size_filter):
    if pack_size_filter is not None:
        filter_value, filter_unit = pack_size_filter
        if product["pack_size"] is None or filter_unit is None:
            if not product["is_loose"]:
                return None
        else:
            converted = _convert_measure(
                filter_value, filter_unit, product["pack_unit"]
            )
            if converted != product["pack_size"] and not product["is_loose"]:
                return None

    quantity, unit = _line_quantity(
        product, requested_quantity, requested_unit
    )
    if quantity is None:
        return None

    if isinstance(quantity, float) and quantity.is_integer():
        quantity = int(quantity)

    line = {"sku": product["sku"], "quantity": quantity}
    try:
        normalised = order_engine.validate_order_items([line])[0]
    except ValueError:
        return None

    live = order_engine.get_product(product["sku"])
    return {
        "sku": live["sku"],
        "item": live["item"],
        "unit": live["unit"],
        "quantity": normalised["quantity"],
        "price": live["price"],
        "pack_size": product["pack_size"],
        "pack_unit": product["pack_unit"],
        "is_loose": product["is_loose"],
        "available": live["stock"],
        "in_stock": normalised["quantity"] <= live["stock"],
    }


def approved_substitutes(sku):
    product = order_engine.get_product(sku)
    if product is None:
        return []

    options = []
    for substitute_sku in product["substitutes"]:
        substitute = order_engine.get_product(substitute_sku)
        if substitute is None:
            continue
        options.append({
            "sku": substitute["sku"],
            "item": substitute["item"],
            "unit": substitute["unit"],
            "stock": substitute["stock"],
            "price": substitute["price"],
        })
    return options


def _finalise_mention(parsed, candidates):
    mention = {
        "raw": parsed["raw"],
        "query": parsed["query"],
        "requested_quantity": parsed["requested_quantity"],
        "requested_unit": parsed["requested_unit"],
        "pack_size_filter": parsed.get("pack_size_filter"),
        "status": "unsupported",
        "candidates": [],
        "resolved": None,
        "in_stock": None,
        "available": None,
        "substitutes": [],
    }

    if not parsed["query"]:
        return mention

    mention["candidates"] = candidates

    if not candidates:
        mention["status"] = "unsupported"
        return mention

    if len(candidates) > 1:
        mention["status"] = "ambiguous"
        return mention

    chosen = candidates[0]
    mention["status"] = "resolved"
    mention["resolved"] = {
        "sku": chosen["sku"],
        "quantity": chosen["quantity"],
        "unit": chosen["unit"],
        "item": chosen["item"],
    }
    mention["in_stock"] = chosen["in_stock"]
    mention["available"] = chosen["available"]
    if not chosen["in_stock"]:
        mention["substitutes"] = approved_substitutes(chosen["sku"])
    return mention


def resolve_mention(clause, sku_whitelist=None):
    parsed = parse_clause(clause)
    products = find_products(parsed["query"], sku_whitelist=sku_whitelist)
    candidates = []
    for product in products:
        candidate = _validated_candidate(
            product,
            parsed["requested_quantity"],
            parsed["requested_unit"],
            parsed["pack_size_filter"],
        )
        if candidate is not None:
            candidates.append(candidate)
    return _finalise_mention(parsed, candidates)


def resolve_text(text, customer_id=None):
    """Parse a customer message into structured catalogue matches."""
    if customer_id is not None and USUAL_RE.search(normalize_text(text) or ""):
        leftover = USUAL_RE.sub(" ", normalize_text(text)).strip()
        if not leftover:
            return {
                "text": text,
                "customer_id": customer_id,
                "mentions": parse_usual_order(customer_id),
            }

    mentions = [resolve_mention(clause) for clause in split_clauses(text)]
    return {
        "text": text,
        "customer_id": customer_id,
        "mentions": mentions,
    }


def parse_usual_order(customer_id):
    customer = order_engine.get_customer(customer_id)
    if customer is None:
        raise ValueError("Unknown customer")

    usual = customer.get("usual_order") or ""
    return [resolve_mention(clause) for clause in split_clauses(usual)]


def apply_clarification(mention, selection):
    """Resolve an ambiguous mention from a SKU id or product description."""
    if not mention or mention.get("status") != "ambiguous":
        return mention

    whitelist = [candidate["sku"] for candidate in mention.get("candidates") or []]
    selected = (selection or "").strip()
    sku_match = re.match(r"^SKU-\d+$", selected, re.I)
    quantity = mention.get("requested_quantity")
    unit = mention.get("requested_unit")
    size_filter = mention.get("pack_size_filter")

    if sku_match:
        products = [
            product
            for product in _catalogue_index()
            if product["sku"].upper() == selected.upper()
            and product["sku"] in whitelist
        ]
        query = selected
    else:
        parsed_selection = parse_clause(selected)
        query = parsed_selection["query"] or normalize_text(selected)
        products = find_products(query, sku_whitelist=whitelist)

    candidates = []
    for product in products:
        candidate = _validated_candidate(product, quantity, unit, size_filter)
        if candidate is not None:
            candidates.append(candidate)

    parsed = {
        "raw": mention.get("raw"),
        "query": query,
        "requested_quantity": quantity,
        "requested_unit": unit,
        "pack_size_filter": size_filter,
    }
    return _finalise_mention(parsed, candidates)
