from order_engine import (
    confirm_order,
    review_order,
    get_approval_queue,
    get_product
)

# TEST 1: NORMAL ORDER
print("===== NORMAL ORDER =====")

normal_order = confirm_order("C006", [
    {"sku": "SKU-014", "quantity": 1},
    {"sku": "SKU-017", "quantity": 5}
])

assert normal_order["status"] == "confirmed"
assert normal_order["total"] == 185
assert get_product("SKU-014")["stock"] == 59

print("Order:", normal_order["order_id"])
print("Status:", normal_order["status"])
print("Total: Rs.", normal_order["total"])
print("Fortune oil remaining:",
      get_product("SKU-014")["stock"])
print("Packing list:", normal_order["packing_list"])


# TEST 2: CREDIT APPROVAL
print("\n===== CREDIT APPROVAL =====")

credit_order = confirm_order("C001", [
    {"sku": "SKU-005", "quantity": 1},
    {"sku": "SKU-009", "quantity": 2},
    {"sku": "SKU-014", "quantity": 1},
    {"sku": "SKU-023", "quantity": 1}
])

assert credit_order["status"] == "awaiting_owner_approval"
assert credit_order["total"] == 880
assert get_product("SKU-005")["stock"] == 25

print("Order:", credit_order["order_id"])
print("Status:", credit_order["status"])
print("Total: Rs.", credit_order["total"])
print("Reasons:", credit_order["approval_reasons"])


# TEST 3: APPROVAL QUEUE
print("\n===== RAMESH'S APPROVAL QUEUE =====")

queue = get_approval_queue()

assert len(queue) == 1
print("Pending orders:", len(queue))


# TEST 4: OWNER APPROVES
print("\n===== OWNER APPROVAL =====")

approved = review_order(
    credit_order["order_id"],
    approve=True
)

assert approved["status"] == "confirmed"
assert get_product("SKU-005")["stock"] == 24
assert len(get_approval_queue()) == 0

print("Order:", approved["order_id"])
print("Status:", approved["status"])
print("Aashirvaad atta remaining:",
      get_product("SKU-005")["stock"])
print("Pending orders:",
      len(get_approval_queue()))

print("\nALL WORKFLOW TESTS PASSED!")
