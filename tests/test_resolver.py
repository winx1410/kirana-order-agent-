from order_engine import validate_order_items
from resolver import (
    apply_clarification,
    approved_substitutes,
    find_products,
    parse_usual_order,
    resolve_text,
)


def skus(mention):
    return [candidate["sku"] for candidate in mention["candidates"]]


def test_sugar_aliases_resolve_to_sku_001():
    for phrase in ("2 kg sugar", "chini 2 kilo", "cheeni 2 kg", "2 kg shakkar"):
        mention = resolve_text(phrase)["mentions"][0]
        assert mention["status"] == "resolved"
        assert mention["resolved"]["sku"] == "SKU-001"
        assert mention["resolved"]["quantity"] == 2
        assert mention["resolved"]["unit"] == "kg"


def test_five_kg_rice_stays_ambiguous_and_basmati_is_five_packs():
    mention = resolve_text("5 kg rice")["mentions"][0]

    assert mention["status"] == "ambiguous"
    assert set(skus(mention)) == {"SKU-002", "SKU-003", "SKU-004"}

    by_sku = {candidate["sku"]: candidate for candidate in mention["candidates"]}
    assert by_sku["SKU-002"]["quantity"] == 5
    assert by_sku["SKU-002"]["unit"] == "kg"
    assert by_sku["SKU-003"]["quantity"] == 5
    assert by_sku["SKU-003"]["unit"] == "kg"
    assert by_sku["SKU-004"]["quantity"] == 5
    assert by_sku["SKU-004"]["unit"] == "pack"
    assert by_sku["SKU-004"]["item"] == "India Gate Basmati Rice, 1 kg"


def test_official_message_confirms_sugar_and_asks_about_rice():
    result = resolve_text("bhaiya 2 kg sugar, 5 kg rice send kar do")
    sugar, rice = result["mentions"]

    assert sugar["status"] == "resolved"
    assert sugar["resolved"]["sku"] == "SKU-001"
    assert rice["status"] == "ambiguous"
    assert set(skus(rice)) == {"SKU-002", "SKU-003", "SKU-004"}


def test_fortune_oil_one_litre_is_sku_014():
    mention = resolve_text("1 litre Fortune oil")["mentions"][0]

    assert mention["status"] == "resolved"
    assert mention["resolved"]["sku"] == "SKU-014"
    assert mention["resolved"]["quantity"] == 1
    assert mention["resolved"]["unit"] == "pouch"
    validate_order_items([mention["resolved"]])


def test_chini_and_tel_resolves_sugar_keeps_oil_ambiguous():
    result = resolve_text("chini 2 kilo aur tel ek litre")
    sugar, oil = result["mentions"]

    assert sugar["status"] == "resolved"
    assert sugar["resolved"]["sku"] == "SKU-001"
    assert sugar["resolved"]["quantity"] == 2
    assert oil["status"] == "ambiguous"
    assert set(skus(oil)) == {"SKU-014", "SKU-015", "SKU-016"}
    assert oil["resolved"] is None


def test_paneer_is_unsupported_and_does_not_guess_dairy():
    result = resolve_text("1 kg paneer aur 2 Lay's")
    paneer, chips = result["mentions"]

    assert paneer["status"] == "unsupported"
    assert paneer["candidates"] == []
    assert paneer["resolved"] is None
    assert chips["status"] == "resolved"
    assert chips["resolved"]["sku"] == "SKU-022"
    assert chips["resolved"]["quantity"] == 2


def test_parle_g_without_unit_is_five_packs():
    mention = resolve_text("5 Parle-G")["mentions"][0]

    assert mention["status"] == "resolved"
    assert mention["resolved"]["sku"] == "SKU-017"
    assert mention["resolved"]["quantity"] == 5
    assert mention["resolved"]["unit"] == "pack"


def test_five_packs_unit_expression():
    mention = resolve_text("5 packs Parle-G")["mentions"][0]
    assert mention["resolved"]["sku"] == "SKU-017"
    assert mention["resolved"]["quantity"] == 5


def test_aashirvaad_5kg_atta_is_one_five_kilo_pack():
    mention = resolve_text("Aashirvaad 5 kg atta")["mentions"][0]

    assert mention["status"] == "resolved"
    assert mention["resolved"]["sku"] == "SKU-005"
    assert mention["resolved"]["quantity"] == 1
    assert mention["resolved"]["unit"] == "pack"


def test_regional_aliases_from_catalogue():
    assert find_products("biyyam")
    assert {product["sku"] for product in find_products("biyyam")} <= {
        "SKU-002",
        "SKU-003",
        "SKU-004",
    }
    assert find_products("nune")
    assert {product["sku"] for product in find_products("kandi pappu")} == {"SKU-009"}
    assert find_products("atta")
    assert find_products("chawal")
    assert find_products("pappu")


def test_surf_excel_out_of_stock_lists_approved_substitutes_only():
    mention = resolve_text("2 Surf Excel 1kg")["mentions"][0]

    assert mention["status"] == "resolved"
    assert mention["resolved"]["sku"] == "SKU-029"
    assert mention["in_stock"] is False
    assert mention["available"] == 0
    assert [option["sku"] for option in mention["substitutes"]] == [
        "SKU-030",
        "SKU-031",
    ]
    assert mention["resolved"]["sku"] != "SKU-030"


def test_short_maggi_offers_yippee_without_replacing():
    mention = resolve_text("4 Maggi noodles")["mentions"][0]

    assert mention["resolved"]["sku"] == "SKU-020"
    assert mention["in_stock"] is False
    assert mention["substitutes"][0]["sku"] == "SKU-021"
    assert mention["resolved"]["sku"] == "SKU-020"


def test_approved_substitutes_never_invent_skus():
    options = approved_substitutes("SKU-001")
    assert options == []
    options = approved_substitutes("SKU-014")
    assert [option["sku"] for option in options] == ["SKU-015", "SKU-016"]


def test_clarification_picks_sona_masoori_from_rice_candidates():
    rice = resolve_text("5 kg rice")["mentions"][0]
    chosen = apply_clarification(rice, "Sona Masoori")

    assert chosen["status"] == "resolved"
    assert chosen["resolved"]["sku"] == "SKU-002"
    assert chosen["resolved"]["quantity"] == 5
    validate_order_items([chosen["resolved"]])


def test_clarification_by_sku_handles_basmati_pack():
    rice = resolve_text("5 kg rice")["mentions"][0]
    chosen = apply_clarification(rice, "SKU-004")

    assert chosen["resolved"]["sku"] == "SKU-004"
    assert chosen["resolved"]["quantity"] == 5
    assert chosen["resolved"]["unit"] == "pack"


def test_usual_order_c001():
    mentions = parse_usual_order("C001")
    assert [mention["resolved"]["sku"] for mention in mentions] == [
        "SKU-001",
        "SKU-014",
        "SKU-023",
        "SKU-017",
    ]
    assert [mention["resolved"]["quantity"] for mention in mentions] == [2, 1, 1, 2]


def test_usual_order_c004():
    mentions = parse_usual_order("C004")
    assert [mention["status"] for mention in mentions] == ["resolved"] * 5
    assert [mention["resolved"]["sku"] for mention in mentions] == [
        "SKU-001",
        "SKU-024",
        "SKU-017",
        "SKU-028",
        "SKU-027",
    ]


def test_usual_order_c006():
    mentions = parse_usual_order("C006")
    assert [mention["resolved"]["sku"] for mention in mentions] == [
        "SKU-020",
        "SKU-022",
        "SKU-025",
    ]
    assert [mention["resolved"]["quantity"] for mention in mentions] == [4, 2, 1]


def test_all_seven_usual_orders_fully_resolve():
    expected = {
        "C001": ["SKU-001", "SKU-014", "SKU-023", "SKU-017"],
        "C002": ["SKU-002", "SKU-009", "SKU-015", "SKU-033"],
        "C003": ["SKU-004", "SKU-016", "SKU-023"],
        "C004": ["SKU-001", "SKU-024", "SKU-017", "SKU-028", "SKU-027"],
        "C005": ["SKU-006", "SKU-002", "SKU-009", "SKU-012"],
        "C006": ["SKU-020", "SKU-022", "SKU-025"],
        "C007": ["SKU-001", "SKU-017"],
    }
    for customer_id, skus_expected in expected.items():
        mentions = parse_usual_order(customer_id)
        assert [mention["status"] for mention in mentions] == ["resolved"] * len(
            skus_expected
        )
        assert [mention["resolved"]["sku"] for mention in mentions] == skus_expected
        for mention in mentions:
            validate_order_items([
                {
                    "sku": mention["resolved"]["sku"],
                    "quantity": mention["resolved"]["quantity"],
                }
            ])


def test_unknown_product_does_not_invent_a_sku():
    mention = resolve_text("1 kg paneer")["mentions"][0]
    assert mention["status"] == "unsupported"
    assert "SKU-" not in (mention["query"] or "")
    assert find_products("iphone") == []


def test_resolved_lines_are_valid_for_order_engine():
    mention = resolve_text("1 litre Fortune oil and 5 Parle-G")
    lines = [
        {
            "sku": item["resolved"]["sku"],
            "quantity": item["resolved"]["quantity"],
        }
        for item in mention["mentions"]
    ]
    assert validate_order_items(lines)[0]["sku"] == "SKU-014"
    from order_engine import calculate_total

    assert calculate_total(lines) == 185
