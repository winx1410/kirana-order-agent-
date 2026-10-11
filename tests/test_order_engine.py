import pytest

import order_engine
from order_engine import (
    calculate_total,
    cancel_order,
    check_stock,
    confirm_order,
    create_draft_order,
    get_approval_queue,
    get_customer,
    get_product,
    prepare_order,
    review_order,
    validate_order_items,
)


CLEAN_ITEMS = [
    {"sku": "SKU-014", "quantity": 1},
    {"sku": "SKU-017", "quantity": 5},
]

CREDIT_ITEMS = [
    {"sku": "SKU-005", "quantity": 1},
    {"sku": "SKU-009", "quantity": 2},
    {"sku": "SKU-014", "quantity": 1},
    {"sku": "SKU-023", "quantity": 1},
]


def test_clean_order_total_is_185():
    assert calculate_total(CLEAN_ITEMS) == 185


def test_stock_shortage_reports_available_units_and_substitutes():
    shortages = check_stock([{"sku": "SKU-020", "quantity": 4}])

    assert len(shortages) == 1
    assert shortages[0]["sku"] == "SKU-020"
    assert shortages[0]["requested"] == 4
    assert shortages[0]["available"] == 3
    assert shortages[0]["substitutes"] == ["SKU-021"]

    result = confirm_order("C006", [{"sku": "SKU-020", "quantity": 4}])
    assert result["status"] == "stock_issue"
    assert get_product("SKU-020")["stock"] == 3


def test_surf_excel_out_of_stock_offers_approved_substitutes():
    result = confirm_order("C003", [{"sku": "SKU-029", "quantity": 2}])

    assert result["status"] == "stock_issue"
    assert result["shortages"][0]["sku"] == "SKU-029"
    assert result["shortages"][0]["available"] == 0
    assert result["shortages"][0]["substitutes"] == ["SKU-030", "SKU-031"]
    assert get_product("SKU-029")["stock"] == 0
    assert order_engine.orders == {}


def test_credit_limit_requires_owner_approval_without_reserving_stock():
    result = confirm_order("C001", CREDIT_ITEMS)

    assert result["status"] == "awaiting_owner_approval"
    assert result["total"] == 880
    assert "Customer credit limit exceeded" in result["approval_reasons"]
    assert result["agent_recommendation"]
    assert get_product("SKU-005")["stock"] == 25
    assert get_customer("C001")["outstanding"] == 4800


def test_normal_order_confirms_and_reserves_stock():
    normal_order = confirm_order("C006", CLEAN_ITEMS)

    assert normal_order["status"] == "confirmed"
    assert normal_order["total"] == 185
    assert get_product("SKU-014")["stock"] == 59
    assert normal_order["packing_list"] == [
        {
            "sku": "SKU-014",
            "item": "Fortune Sunflower Oil, 1 L",
            "quantity": 1,
            "unit": "pouch",
        },
        {
            "sku": "SKU-017",
            "item": "Parle-G Biscuits, 56 g",
            "quantity": 5,
            "unit": "pack",
        },
    ]


def test_credit_order_is_placed_on_ramesh_queue():
    credit_order = confirm_order("C001", CREDIT_ITEMS)
    queue = get_approval_queue()

    assert credit_order["status"] == "awaiting_owner_approval"
    assert len(queue) == 1
    assert queue[0]["order_id"] == credit_order["order_id"]
    assert queue[0]["order"]["order_id"] == credit_order["order_id"]
    assert "Customer credit limit exceeded" in queue[0]["approval_reasons"]
    assert queue[0]["agent_recommendation"]
    assert "exceed" in queue[0]["agent_recommendation"].lower()


def test_owner_approval_confirms_order_and_deducts_stock():
    credit_order = confirm_order("C001", CREDIT_ITEMS)
    approved = review_order(credit_order["order_id"], approve=True)

    assert approved["status"] == "confirmed"
    assert get_product("SKU-005")["stock"] == 24
    assert get_customer("C001")["outstanding"] == 5680
    assert len(get_approval_queue()) == 0


def test_owner_rejection_does_not_change_stock_or_credit():
    credit_order = confirm_order("C001", CREDIT_ITEMS)
    rejected = review_order(credit_order["order_id"], approve=False)

    assert rejected["status"] == "rejected"
    assert get_product("SKU-005")["stock"] == 25
    assert get_product("SKU-009")["stock"] == 80
    assert get_customer("C001")["outstanding"] == 4800
    assert len(get_approval_queue()) == 0
    assert credit_order["order_id"] not in order_engine.approval_queue


def test_review_order_stock_shortage_updates_the_same_pending_order():
    credit_order = confirm_order("C001", CREDIT_ITEMS)
    get_product("SKU-005")["stock"] = 0

    reviewed = review_order(credit_order["order_id"], approve=True)

    assert reviewed["order_id"] == credit_order["order_id"]
    assert reviewed["status"] == "stock_issue"
    assert reviewed["shortages"][0]["sku"] == "SKU-005"
    assert reviewed is order_engine.orders[credit_order["order_id"]]
    assert credit_order["order_id"] in order_engine.approval_queue
    assert get_product("SKU-005")["stock"] == 0
    assert get_customer("C001")["outstanding"] == 4800


def test_owner_can_retry_after_stock_returns():
    credit_order = confirm_order("C001", CREDIT_ITEMS)
    get_product("SKU-005")["stock"] = 0
    review_order(credit_order["order_id"], approve=True)

    get_product("SKU-005")["stock"] = 25
    approved = review_order(credit_order["order_id"], approve=True)

    assert approved["status"] == "confirmed"
    assert get_product("SKU-005")["stock"] == 24
    assert len(get_approval_queue()) == 0


def test_cancel_pending_order_does_not_change_stock_or_credit():
    credit_order = confirm_order("C001", CREDIT_ITEMS)
    cancelled = cancel_order(credit_order["order_id"])

    assert cancelled["status"] == "cancelled"
    assert get_product("SKU-005")["stock"] == 25
    assert get_customer("C001")["outstanding"] == 4800
    assert len(get_approval_queue()) == 0


def test_cancel_draft_order_does_not_reserve_stock():
    draft = create_draft_order("C006", CLEAN_ITEMS)

    assert draft["status"] == "awaiting_customer_confirmation"
    assert get_product("SKU-014")["stock"] == 60

    cancelled = cancel_order(draft["order_id"])

    assert cancelled["status"] == "cancelled"
    assert get_product("SKU-014")["stock"] == 60
    assert get_product("SKU-017")["stock"] == 200


def test_cannot_cancel_confirmed_order():
    normal_order = confirm_order("C006", CLEAN_ITEMS)

    with pytest.raises(ValueError, match="pending"):
        cancel_order(normal_order["order_id"])

    assert get_product("SKU-014")["stock"] == 59


def test_duplicate_owner_approval_does_not_deduct_stock_twice():
    credit_order = confirm_order("C001", CREDIT_ITEMS)
    first = review_order(credit_order["order_id"], approve=True)
    second = review_order(credit_order["order_id"], approve=True)

    assert first["status"] == "confirmed"
    assert second["status"] == "confirmed"
    assert first["order_id"] == second["order_id"]
    assert get_product("SKU-005")["stock"] == 24
    assert get_customer("C001")["outstanding"] == 5680


def test_duplicate_confirm_of_same_draft_does_not_deduct_twice():
    draft = create_draft_order("C006", CLEAN_ITEMS)
    first = confirm_order("C006", CLEAN_ITEMS, order_id=draft["order_id"])
    second = confirm_order("C006", CLEAN_ITEMS, order_id=draft["order_id"])

    assert first["order_id"] == draft["order_id"]
    assert second["order_id"] == draft["order_id"]
    assert first["status"] == "confirmed"
    assert second["status"] == "confirmed"
    assert get_product("SKU-014")["stock"] == 59
    assert get_product("SKU-017")["stock"] == 195


def test_duplicate_confirm_of_pending_approval_does_not_create_second_order():
    first = confirm_order("C001", CREDIT_ITEMS)
    second = confirm_order("C001", CREDIT_ITEMS, order_id=first["order_id"])

    assert second["order_id"] == first["order_id"]
    assert second["status"] == "awaiting_owner_approval"
    assert len(order_engine.orders) == 1
    assert get_product("SKU-005")["stock"] == 25


def test_state_is_isolated_across_resets():
    confirm_order("C006", CLEAN_ITEMS)
    assert get_product("SKU-014")["stock"] == 59

    order_engine.reset_state()

    assert get_product("SKU-014")["stock"] == 60
    assert get_approval_queue() == []
    assert order_engine.orders == {}
    assert get_customer("C001")["outstanding"] == 4800


def test_cash_order_over_3000_needs_approval_without_reserving_stock():
    items = [{"sku": "SKU-002", "quantity": 50}]
    result = confirm_order("C002", items)

    assert result["total"] == 3100
    assert result["status"] == "awaiting_owner_approval"
    assert "Order exceeds Rs. 3000" in result["approval_reasons"]
    assert "Customer credit limit exceeded" not in result["approval_reasons"]
    assert result["agent_recommendation"]
    assert get_product("SKU-002")["stock"] == 150
    assert get_customer("C002")["outstanding"] == 0


def test_unknown_sku_is_rejected():
    with pytest.raises(ValueError, match="Unknown SKU"):
        calculate_total([{"sku": "SKU-999", "quantity": 1}])


def test_invalid_quantities_are_rejected():
    with pytest.raises(ValueError, match="positive"):
        validate_order_items([{"sku": "SKU-001", "quantity": 0}])

    with pytest.raises(ValueError, match="positive"):
        validate_order_items([{"sku": "SKU-001", "quantity": -1}])

    with pytest.raises(ValueError, match="whole numbers"):
        validate_order_items([{"sku": "SKU-017", "quantity": 1.5}])

    with pytest.raises(ValueError, match="at least one item"):
        validate_order_items([])


def test_loose_kg_allows_fractional_quantity():
    assert calculate_total([{"sku": "SKU-001", "quantity": 0.5}]) == 23


def test_prepare_order_credit_case_is_880():
    preview = prepare_order("C001", CREDIT_ITEMS)

    assert preview["total"] == 880
    assert preview["status"] == "awaiting_owner_approval"
    assert preview["approval"]["approval_required"] is True
    assert preview["agent_recommendation"]
