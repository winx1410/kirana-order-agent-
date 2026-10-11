
import json

# ---------------------------------------
# 1. LOAD DATA
# ---------------------------------------

with open("catalogue.json", "r", encoding="utf-8") as f:
    catalogue = json.load(f)

with open("customers.json", "r", encoding="utf-8") as f:
    customers = json.load(f)


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


# ---------------------------------------
# 4. CALCULATE ORDER TOTAL
# ---------------------------------------

def calculate_total(order_items):
    total = 0

    for order_item in order_items:
        product = get_product(order_item["sku"])

        if product is None:
            raise ValueError("Unknown SKU: " + order_item["sku"])

        quantity = order_item["quantity"]

        if isinstance(quantity, bool) or not isinstance(
            quantity, (int, float)
        ) or quantity <= 0:
            raise ValueError("Quantity must be positive")

        if product["unit"] != "kg" and not float(
            quantity
        ).is_integer():
            raise ValueError("Pack quantities must be whole numbers")

        total += product["price"] * quantity

    return total


# ---------------------------------------
# 5. CHECK STOCK
# ---------------------------------------

def check_stock(order_items):
    shortages = []
    required = {}

    for order_item in order_items:
        sku = order_item["sku"]
        required[sku] = required.get(
            sku, 0
        ) + order_item["quantity"]

    for sku, quantity in required.items():
        product = get_product(sku)

        if product is None:
            raise ValueError("Unknown SKU: " + sku)

        if quantity > product["stock"]:
            shortages.append({
                "sku": sku,
                "item": product["item"],
                "requested": quantity,
                "available": product["stock"],
                "substitutes": product["substitutes"]
            })

    return shortages


# ---------------------------------------
# 6. CHECK APPROVAL RULES
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
        "reasons": reasons
    }


# ---------------------------------------
# 7. PREPARE ORDER
# ---------------------------------------

def prepare_order(customer_id, order_items):
    customer = get_customer(customer_id)

    if customer is None:
        raise ValueError("Unknown customer")

    total = calculate_total(order_items)
    shortages = check_stock(order_items)
    approval = check_approval(customer_id, total)

    if shortages:
        status = "stock_issue"
    elif approval["approval_required"]:
        status = "awaiting_owner_approval"
    else:
        status = "awaiting_customer_confirmation"

    return {
        "customer_id": customer_id,
        "customer": customer["name"],
        "items": order_items,
        "total": total,
        "shortages": shortages,
        "approval": approval,
        "status": status
    }


# ---------------------------------------
# 8. ORDER MANAGEMENT (IN MEMORY)
# ---------------------------------------

orders = {}
approval_queue = {}
next_order_number = 1


def reserve_stock(order_items):
    """Deduct inventory for a confirmed order."""
    shortages = check_stock(order_items)

    if shortages:
        raise ValueError("Insufficient stock")

    for line in order_items:
        product = get_product(line["sku"])
        product["stock"] -= line["quantity"]


def build_packing_list(order_items):
    """Create a staff-friendly picking list."""
    packing_list = []

    for line in order_items:
        product = get_product(line["sku"])
        packing_list.append({
            "sku": line["sku"],
            "item": product["item"],
            "quantity": line["quantity"],
            "unit": product["unit"]
        })

    return packing_list


def confirm_order(customer_id, order_items):
    """
    Call only after the customer has explicitly
    confirmed the final order and any substitutions.
    """
    global next_order_number

    # Revalidate using current prices and inventory
    result = prepare_order(customer_id, order_items)

    if result["shortages"]:
        return {
            "status": "stock_issue",
            "shortages": result["shortages"]
        }

    order_id = f"ORD-{next_order_number:04d}"
    next_order_number += 1

    order = {
        "order_id": order_id,
        "customer_id": customer_id,
        "customer": result["customer"],
        "items": [
            dict(line) for line in order_items
        ],
        "total": result["total"],
        "packing_list": build_packing_list(order_items),
        "approval_reasons": result["approval"]["reasons"],
        "status": None
    }

    if result["approval"]["approval_required"]:
        order["status"] = "awaiting_owner_approval"
        orders[order_id] = order
        approval_queue[order_id] = order

    else:
        reserve_stock(order_items)
        order["status"] = "confirmed"
        orders[order_id] = order

        customer = get_customer(customer_id)
        if customer["payment_type"].lower() == "credit":
            customer["outstanding"] += result["total"]

    return order


# ---------------------------------------
# 9. OWNER APPROVAL
# ---------------------------------------

def review_order(order_id, approve):
    if order_id not in approval_queue:
        raise ValueError("Order not awaiting approval")

    order = approval_queue[order_id]

    if not approve:
        order["status"] = "rejected"
        del approval_queue[order_id]
        return order

    # Stock may have changed while awaiting approval
    shortages = check_stock(order["items"])

    if shortages:
        return {
            "order_id": order_id,
            "status": "stock_issue",
            "shortages": shortages
        }

    # Owner has explicitly approved the risk
    reserve_stock(order["items"])

    customer = get_customer(order["customer_id"])
    if customer["payment_type"].lower() == "credit":
        customer["outstanding"] += order["total"]

    order["status"] = "confirmed"
    del approval_queue[order_id]

    return order


def get_approval_queue():
    return list(approval_queue.values())
