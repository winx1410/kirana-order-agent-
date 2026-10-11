import copy
import json
from pathlib import Path

# ---------------------------------------
# 1. LOAD DATA
# ---------------------------------------

_DATA_DIR = Path(__file__).resolve().parent

with open(_DATA_DIR / "catalogue.json", "r", encoding="utf-8") as f:
    _CATALOGUE_SEED = json.load(f)

with open(_DATA_DIR / "customers.json", "r", encoding="utf-8") as f:
    _CUSTOMERS_SEED = json.load(f)

catalogue = []
customers = []
orders = {}
approval_queue = {}
next_order_number = 1

_CANCELLABLE_STATUSES = {
    "awaiting_customer_confirmation",
    "awaiting_owner_approval",
    "stock_issue",
}


def reset_state():
    """Reload catalogue, customers and empty order state.

    Automated tests call this so inventory and credit balances
    do not leak between cases.
    """
    global catalogue, customers, orders, approval_queue, next_order_number

    catalogue = copy.deepcopy(_CATALOGUE_SEED)
    customers = copy.deepcopy(_CUSTOMERS_SEED)
    orders = {}
    approval_queue = {}
    next_order_number = 1


reset_state()


# ---------------------------------------
# 2. FIND PRODUCT BY SKU
# ---------------------------------------

def get_product(sku):
    for product in catalogue:
        if product["sku"] == sku:
            return product
    return None


# ---------------------------------------
# 3. FIND CUSTOMER
# ---------------------------------------

def get_customer(customer_id):
    for customer in customers:
        if customer["customer_id"] == customer_id:
            return customer
    return None


def get_order(order_id):
    return orders.get(order_id)


# ---------------------------------------
# 4. LINE VALIDATION
# ---------------------------------------

def _format_rupees(amount):
    if isinstance(amount, (int, float)) and float(amount).is_integer():
        return str(int(amount))
    return str(amount)


def validate_quantity(quantity, unit):
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
        raise ValueError("Quantity must be a positive number")

    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    if unit != "kg" and not float(quantity).is_integer():
        raise ValueError("Pack quantities must be whole numbers")

    return quantity


def validate_order_items(order_items):
    """Reject unknown SKUs, empty baskets and illegal quantities."""
    if not order_items:
        raise ValueError("Order must contain at least one item")

    if not isinstance(order_items, (list, tuple)):
        raise ValueError("Order items must be a list")

    normalised = []
    merged = {}

    for line in order_items:
        if not isinstance(line, dict):
            raise ValueError("Each order line must be an object")

        sku = line.get("sku")
        if not sku or not isinstance(sku, str):
            raise ValueError("Missing SKU")

        product = get_product(sku)
        if product is None:
            raise ValueError("Unknown SKU: " + str(sku))

        if "quantity" not in line:
            raise ValueError("Missing quantity for " + sku)

        quantity = validate_quantity(line["quantity"], product["unit"])
        merged[sku] = merged.get(sku, 0) + quantity

    for sku, quantity in merged.items():
        product = get_product(sku)
        validate_quantity(quantity, product["unit"])
        normalised.append({"sku": sku, "quantity": quantity})

    return normalised


# ---------------------------------------
# 5. CALCULATE ORDER TOTAL
# ---------------------------------------

def calculate_total(order_items):
    lines = validate_order_items(order_items)
    total = 0

    for order_item in lines:
        product = get_product(order_item["sku"])
        total += product["price"] * order_item["quantity"]

    return total


# ---------------------------------------
# 6. CHECK STOCK
# ---------------------------------------

def check_stock(order_items):
    lines = validate_order_items(order_items)
    shortages = []
    required = {}

    for order_item in lines:
        sku = order_item["sku"]
        required[sku] = required.get(sku, 0) + order_item["quantity"]

    for sku, quantity in required.items():
        product = get_product(sku)

        if quantity > product["stock"]:
            shortages.append({
                "sku": sku,
                "item": product["item"],
                "requested": quantity,
                "available": product["stock"],
                "substitutes": list(product["substitutes"]),
            })

    return shortages


# ---------------------------------------
# 7. CHECK APPROVAL RULES
# ---------------------------------------

def check_approval(customer_id, total):
    customer = get_customer(customer_id)

    if customer is None:
        raise ValueError("Unknown customer")

    reasons = []

    if total > 3000:
        reasons.append("Order exceeds Rs. 3000")

    if customer["payment_type"].lower() == "credit":
        projected_balance = customer["outstanding"] + total

        if projected_balance > customer["credit_limit"]:
            reasons.append("Customer credit limit exceeded")

    return {
        "approval_required": len(reasons) > 0,
        "reasons": reasons,
    }


def build_agent_recommendation(customer, total, reasons):
    """Deterministic note for Ramesh's approval queue (Section 5)."""
    if not reasons:
        return None

    name = customer["name"]
    bill = _format_rupees(total)
    parts = []

    if "Customer credit limit exceeded" in reasons:
        overshoot = customer["outstanding"] + total - customer["credit_limit"]
        parts.append(
            "Do not auto-confirm. "
            + name
            + "'s outstanding Rs."
            + _format_rupees(customer["outstanding"])
            + " plus this bill Rs."
            + bill
            + " exceeds the Rs."
            + _format_rupees(customer["credit_limit"])
            + " credit limit by Rs."
            + _format_rupees(overshoot)
            + ". Recommend collecting payment or approving only if you accept the extra credit."
        )

    if "Order exceeds Rs. 3000" in reasons:
        parts.append(
            "Recommend reviewing this Rs."
            + bill
            + " order before packing; it is above the Rs.3,000 auto-confirm threshold."
        )

    return " ".join(parts)


# ---------------------------------------
# 8. PREPARE ORDER
# ---------------------------------------

def prepare_order(customer_id, order_items):
    customer = get_customer(customer_id)

    if customer is None:
        raise ValueError("Unknown customer")

    lines = validate_order_items(order_items)
    total = calculate_total(lines)
    shortages = check_stock(lines)
    approval = check_approval(customer_id, total)
    recommendation = build_agent_recommendation(
        customer, total, approval["reasons"]
    )

    if shortages:
        status = "stock_issue"
    elif approval["approval_required"]:
        status = "awaiting_owner_approval"
    else:
        status = "awaiting_customer_confirmation"

    return {
        "customer_id": customer_id,
        "customer": customer["name"],
        "items": lines,
        "total": total,
        "shortages": shortages,
        "approval": approval,
        "agent_recommendation": recommendation,
        "status": status,
    }


# ---------------------------------------
# 9. ORDER MANAGEMENT (IN MEMORY)
# ---------------------------------------

def reserve_stock(order_items):
    """Deduct inventory for a confirmed order."""
    lines = validate_order_items(order_items)
    shortages = check_stock(lines)

    if shortages:
        raise ValueError("Insufficient stock")

    for line in lines:
        product = get_product(line["sku"])
        product["stock"] -= line["quantity"]


def restore_stock(order_items):
    """Return reserved units to inventory."""
    lines = validate_order_items(order_items)

    for line in lines:
        product = get_product(line["sku"])
        product["stock"] += line["quantity"]


def build_packing_list(order_items):
    """Create a staff-friendly picking list."""
    lines = validate_order_items(order_items)
    packing_list = []

    for line in lines:
        product = get_product(line["sku"])
        packing_list.append({
            "sku": line["sku"],
            "item": product["item"],
            "quantity": line["quantity"],
            "unit": product["unit"],
        })

    return packing_list


def _apply_outstanding(order):
    if order.get("outstanding_applied"):
        return

    customer = get_customer(order["customer_id"])
    if customer["payment_type"].lower() == "credit":
        customer["outstanding"] += order["total"]
        order["outstanding_applied"] = True


def _reverse_outstanding(order):
    if not order.get("outstanding_applied"):
        return

    customer = get_customer(order["customer_id"])
    if customer["payment_type"].lower() == "credit":
        customer["outstanding"] -= order["total"]
        order["outstanding_applied"] = False


def _reserve_and_charge(order):
    """Reserve stock and apply credit once. Safe to call again."""
    if order.get("stock_reserved"):
        _apply_outstanding(order)
        order["status"] = "confirmed"
        order["shortages"] = []
        return order

    shortages = check_stock(order["items"])
    if shortages:
        order["status"] = "stock_issue"
        order["shortages"] = shortages
        return order

    reserve_stock(order["items"])
    order["stock_reserved"] = True
    order["shortages"] = []
    _apply_outstanding(order)
    order["status"] = "confirmed"
    return order


def _next_order_id():
    global next_order_number

    order_id = f"ORD-{next_order_number:04d}"
    next_order_number += 1
    return order_id


def _new_order_record(customer_id, result, status):
    return {
        "order_id": _next_order_id(),
        "customer_id": customer_id,
        "customer": result["customer"],
        "items": [dict(line) for line in result["items"]],
        "total": result["total"],
        "packing_list": build_packing_list(result["items"]),
        "approval_reasons": list(result["approval"]["reasons"]),
        "agent_recommendation": result["agent_recommendation"],
        "shortages": list(result["shortages"]),
        "stock_reserved": False,
        "outstanding_applied": False,
        "status": status,
    }


def create_draft_order(customer_id, order_items):
    """Persist a draft bill. Never reserves stock."""
    result = prepare_order(customer_id, order_items)

    if result["shortages"]:
        status = "stock_issue"
    else:
        status = "awaiting_customer_confirmation"

    order = _new_order_record(customer_id, result, status)
    orders[order["order_id"]] = order
    return order


def confirm_order(customer_id, order_items, order_id=None):
    """
    Call only after the customer has explicitly
    confirmed the final order and any substitutions.

    Passing order_id makes confirmation and inventory
    deduction idempotent for that order.
    """
    if order_id is not None:
        order = orders.get(order_id)

        if order is None:
            raise ValueError("Unknown order")

        if order["customer_id"] != customer_id:
            raise ValueError("Order does not belong to customer")

        if order["status"] == "confirmed":
            return order

        if order["status"] == "awaiting_owner_approval":
            return order

        if order["status"] in ("cancelled", "rejected"):
            raise ValueError("Cannot confirm a cancelled or rejected order")

        order_items = order["items"]

    result = prepare_order(customer_id, order_items)

    if result["shortages"]:
        if order_id is not None:
            order = orders[order_id]
            order["status"] = "stock_issue"
            order["shortages"] = result["shortages"]
            order["total"] = result["total"]
            return order

        return {
            "status": "stock_issue",
            "shortages": result["shortages"],
        }

    if order_id is None:
        order = _new_order_record(customer_id, result, None)
        orders[order["order_id"]] = order
    else:
        order = orders[order_id]
        order["items"] = [dict(line) for line in result["items"]]
        order["total"] = result["total"]
        order["packing_list"] = build_packing_list(result["items"])
        order["approval_reasons"] = list(result["approval"]["reasons"])
        order["agent_recommendation"] = result["agent_recommendation"]
        order["shortages"] = []

    if result["approval"]["approval_required"]:
        order["status"] = "awaiting_owner_approval"
        approval_queue[order["order_id"]] = order
        return order

    _reserve_and_charge(order)
    return order


# ---------------------------------------
# 10. OWNER APPROVAL
# ---------------------------------------

def review_order(order_id, approve):
    order = orders.get(order_id)

    if order is None:
        raise ValueError("Unknown order")

    if order["status"] == "confirmed":
        return order

    if order["status"] == "rejected":
        return order

    if order_id not in approval_queue:
        raise ValueError("Order not awaiting approval")

    if not approve:
        if order.get("stock_reserved"):
            restore_stock(order["items"])
            order["stock_reserved"] = False
        _reverse_outstanding(order)
        order["status"] = "rejected"
        approval_queue.pop(order_id, None)
        return order

    _reserve_and_charge(order)

    if order["status"] == "confirmed":
        approval_queue.pop(order_id, None)

    return order


def cancel_order(order_id):
    """Cancel a draft or pending order without changing reserved stock."""
    order = orders.get(order_id)

    if order is None:
        raise ValueError("Unknown order")

    if order["status"] not in _CANCELLABLE_STATUSES:
        raise ValueError("Only pending orders can be cancelled")

    if order.get("stock_reserved"):
        restore_stock(order["items"])
        order["stock_reserved"] = False

    _reverse_outstanding(order)
    order["status"] = "cancelled"
    approval_queue.pop(order_id, None)
    return order


def get_approval_queue():
    """Each record is the order plus flag reasons and the agent's recommendation."""
    records = []

    for order in approval_queue.values():
        records.append({
            "order_id": order["order_id"],
            "order": order,
            "approval_reasons": list(order.get("approval_reasons") or []),
            "agent_recommendation": order.get("agent_recommendation"),
            "customer_id": order["customer_id"],
            "customer": order["customer"],
            "items": order["items"],
            "total": order["total"],
            "packing_list": order["packing_list"],
            "status": order["status"],
            "stock_reserved": order.get("stock_reserved", False),
        })

    return records
