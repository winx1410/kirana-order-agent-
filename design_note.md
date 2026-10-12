# Design Note — Kirana Order-Taking Agent

### 1. Problem and priorities

Ramesh manages informal Hindi-English grocery orders while packing goods and serving customers. Four failures matter most: **incorrect or incomplete orders, unauthorized substitutions, unavailable stock being promised, and credit-limit violations**. I prioritized accurate order interpretation, customer confirmation, stock validation, and owner escalation because these directly affect customer trust, operational accuracy, and financial risk.

Analytics questions such as “What's running low?” and “Who owes more than ₹2,000?” were deliberately excluded to keep the implementation focused on completing reliable orders.

### 2. Architecture and tool selection

The solution uses **one conversational agent**, rather than multiple agents, to reduce orchestration complexity.

- **Streamlit (`app.py`, `pages/owner_queue.py`):** Lightweight customer chat and owner dashboard, chosen for rapid development and public deployment.
- **Gemini 3.5 Flash Lite (`nlu.py`):** Extracts structured intent and product mentions from informal multilingual messages.
- **Product resolver (`resolver.py`):** Matches descriptions to the fixed 39-item catalogue, normalizes units, identifies ambiguities, and restricts substitutions to approved alternatives.
- **Conversation controller (`agent.py`):** Maintains draft carts, clarifications, customer consent, order modifications, and confirmations.
- **Deterministic order engine (`order_engine.py`):** Calculates bills, validates stock and credit, handles approval decisions, and generates confirmed packing lists.

**Design principle:** Gemini interprets the customer's language; Python controls SKUs, catalogue prices, inventory and business rules. This prevents the LLM from independently inventing prices or authorizing exceptions.

### 3. Autonomous decisions versus escalation

The agent independently resolves unique in-stock products, prepares carts, calculates bills and explains unsupported items. It never places an order without explicit customer confirmation.

When rice or oil matches multiple products, the agent asks for clarification rather than choosing. Out-of-stock substitutions require explicit customer consent.

Orders are escalated to Ramesh if **outstanding credit + order value exceeds the credit limit**, or the order exceeds **₹3,000**. Cash customers bypass credit checks. Stock is reserved only after customer confirmation and any required owner approval. Ramesh receives the order details, escalation reason and recommendation.

### 4. Evaluation, reliability and trade-offs

The system passed **12/12 automated outcome evaluations** covering the eight official scenarios and four additional edge cases. These used mocked Gemini intents and verified product resolution, totals, clarification, consent, stock changes and approvals. The result measures business-rule correctness under scripted interpretation, **not live Gemini accuracy**.

Known limitations include occasional incomplete unit extraction, API rate-limit or availability errors, and process-local rate limiting. Gemini is called only for new customer messages, with caps of 10 requests/minute and 400 requests/rolling 24 hours. API errors preserve the draft cart.

In-memory orders, stock and credit simplify deployment but reset on application restart. The public owner dashboard has no authentication, as permitted by the assignment. This is a demonstration, not a production system.

### 5. Cost and scope

On the documented free tier, orders within the quota have ₹0 API cost. Using the quoted paid-tier rates, an illustrative order with 1,400 input and 300 output tokens costs approximately **$0.00117**; actual token usage was not measured.

The project was built across phased sessions, without formally tracked development hours. No claim is made about meeting the suggested time budget.

### With another week

I would prioritize database-backed orders, inventory and credit to support persistence and concurrent usage. Next, I would evaluate live Gemini on unseen multilingual and contradictory orders, improve product aliases and unusual-unit handling, and introduce structured monitoring and persistent usage controls. These would improve reliability while retaining deterministic pricing, consent and owner-approval safeguards.
