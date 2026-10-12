"""Ramesh's approval queue.

Uses the same in-memory orders and stock as the customer chat.
This page does not call Gemini.
Restarting Streamlit clears the queue and restores catalogue stock.
"""

import streamlit as st

import order_engine


st.set_page_config(page_title="Ramesh's queue", layout="wide")
st.title("Ramesh's approval queue")
st.caption(
    "Stock is reserved only after you approve. "
    "Orders and stock are kept in memory for this running app and are cleared on restart. "
    "There is no login. The assignment excludes authentication, so anyone with this link can approve or reject."
)

queue = order_engine.get_approval_queue()
if not queue:
    st.info("No orders are waiting.")
else:
    for record in queue:
        order = record["order"]
        with st.container(border=True):
            st.subheader(order["customer"] + " · " + order["order_id"])
            st.write("Total " + "Rs." + str(order["total"]))
            st.write("Reason: " + "; ".join(record["approval_reasons"] or ["—"]))
            if record.get("agent_recommendation"):
                st.write(record["agent_recommendation"])
            for line in order["packing_list"]:
                product = order_engine.get_product(line["sku"])
                price = product["price"] if product else ""
                st.write(
                    str(line["quantity"])
                    + " "
                    + line["unit"]
                    + " "
                    + line["item"]
                    + " · Rs."
                    + str(price)
                )
            approve, reject = st.columns(2)
            if approve.button("Approve", key="approve-" + order["order_id"]):
                reviewed = order_engine.review_order(order["order_id"], approve=True)
                if reviewed["status"] == "confirmed":
                    st.success(order["order_id"] + " is confirmed.")
                else:
                    st.warning(order["order_id"] + " could not be packed yet.")
                st.rerun()
            if reject.button("Reject", key="reject-" + order["order_id"]):
                order_engine.review_order(order["order_id"], approve=False)
                st.warning(order["order_id"] + " was rejected. Stock was not deducted.")
                st.rerun()

st.subheader("Confirmed packing lists")
confirmed = [
    order
    for order in order_engine.orders.values()
    if order["status"] == "confirmed"
]
if not confirmed:
    st.write("No confirmed orders yet.")
for order in confirmed:
    st.markdown("**" + order["order_id"] + " · " + order["customer"] + "**")
    st.write("Total Rs." + str(order["total"]))
    for line in order["packing_list"]:
        st.write(
            "- "
            + str(line["quantity"])
            + " "
            + line["unit"]
            + " "
            + line["item"]
            + " ("
            + line["sku"]
            + ")"
        )
