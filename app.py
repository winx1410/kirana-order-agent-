"""Customer chat for Ramesh's kirana order assistant.

Gemini is called only when the customer submits a new chat message.
Reruns, customer changes, and the owner page do not interpret language.
Orders and stock live in this process. Restarting Streamlit clears them.
"""

import uuid

import streamlit as st

import order_engine
from agent import clarification_question, get_agent


st.set_page_config(page_title="Kirana orders", layout="wide")


def _rupees(amount):
    if isinstance(amount, (int, float)) and float(amount).is_integer():
        return "Rs." + str(int(amount))
    return "Rs." + str(amount)


if "browser_session" not in st.session_state:
    st.session_state.browser_session = uuid.uuid4().hex
if "transcripts" not in st.session_state:
    st.session_state.transcripts = {}

customers = list(order_engine.customers)
labels = {
    customer["customer_id"]: customer["customer_id"] + " · " + customer["name"]
    for customer in customers
}

st.sidebar.title("Customer")
customer_id = st.sidebar.selectbox(
    "Who is ordering",
    options=[customer["customer_id"] for customer in customers],
    format_func=lambda cid: labels[cid],
)
customer = order_engine.get_customer(customer_id)
st.sidebar.caption(
    customer["payment_type"].title()
    + " · outstanding "
    + _rupees(customer["outstanding"])
)

agent = get_agent(customer_id, session_id=st.session_state.browser_session)
agent.sync_status_from_order()
order = order_engine.get_order(agent.order_id) if agent.order_id else None
chat_key = st.session_state.browser_session + ":" + customer_id
transcript = st.session_state.transcripts.setdefault(chat_key, [])

st.title("Order chat")
st.caption("Tell Ramesh's assistant what to pack. Prices come only from the catalogue.")

if agent.status == "awaiting_owner_approval":
    st.info("This order is with Ramesh. It is not confirmed yet.")
elif agent.status == "rejected":
    st.warning("Ramesh rejected this order. Nothing was reserved.")
elif agent.status == "confirmed" and order and order.get("approval_reasons"):
    st.success("Ramesh approved this order. It is confirmed.")
elif agent.status == "confirmed":
    st.success("This order is confirmed.")
elif agent.status == "stock_issue":
    st.warning("This order is waiting because something is short.")
elif agent.status == "awaiting_customer_confirmation":
    st.info("Check the bill, then reply to confirm or change it.")

for message in transcript:
    with st.chat_message(message["role"]):
        st.write(message["text"])

prompt = st.chat_input("For example: 2 kg sugar, 5 kg rice")
if prompt:
    transcript.append({"role": "user", "text": prompt})
    result = agent.handle(prompt)
    transcript.append({"role": "assistant", "text": result["reply"]})
    st.rerun()

st.sidebar.subheader("Cart")
if agent.cart:
    for line in agent.cart:
        st.sidebar.write(
            str(line["quantity"])
            + " "
            + line["unit"]
            + " "
            + line["item"]
        )
        st.sidebar.caption(
            _rupees(line["price"])
            + " each · "
            + _rupees(line["line_total"])
        )
    preview = order_engine.prepare_order(
        customer_id,
        [{"sku": line["sku"], "quantity": line["quantity"]} for line in agent.cart],
    )
    st.sidebar.write("**Total " + _rupees(preview["total"]) + "**")
    st.sidebar.caption("Status: " + agent.status.replace("_", " "))
else:
    st.sidebar.write("No items yet.")

if agent.pending_clarifications:
    st.sidebar.subheader("Please choose")
    for item in agent.pending_clarifications:
        st.sidebar.write(clarification_question(item))

if agent.pending_substitutions:
    st.sidebar.subheader("Approved substitutes")
    for item in agent.pending_substitutions:
        st.sidebar.write(item["item"])
        for option in item.get("substitutes") or []:
            if option.get("stock", 0) <= 0:
                continue
            st.sidebar.caption(
                option["item"] + " · " + _rupees(option["price"])
            )

if agent.order_id:
    st.sidebar.write("Order " + agent.order_id)
