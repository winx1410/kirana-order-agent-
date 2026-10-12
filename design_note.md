# Design note: Ramesh's order-taking assistant

Ramesh takes mixed Hindi-English orders while he is packing and serving the counter. The costly failures are a wrong or incomplete order, a silent substitution, stock promised but not on the shelf, and credit that is discovered only after the goods leave. This build targets those four. "What's running low?" and "who owes more than Rs.2,000?" were left out so the agent could finish a confirmable order and an approval queue.

## Architecture

One Streamlit app, not several agents. `nlu.py` sends the customer message to Gemini 3.5 Flash Lite and accepts only a validated intent: what was said, in the customer's words. `resolver.py` matches those words to the 39 catalogue rows, including loose kilograms versus 1 kg packs. `order_engine.py` owns the bill, stock reservation, credit check, and Ramesh's queue. `agent.py` decides the next step. Prices, stock, and approval never come from the model. That split is the Section 10 boundary between language judgement and deterministic code.

Gemini is called only when the customer submits a new chat message. Reruns, customer switches, and the owner page do not call it. The local cap is 10 requests per rolling minute and 400 per rolling 24 hours, under the free-tier dashboard limits seen earlier for this model (15 per minute and 500 per day). The cap lives in the running process. A restart clears it, and it does not replace Google's own quota. HTTP 429 and 503 stop immediately, leave the cart as it was, and are not retried.

## Who decides

The agent resolves a unique in-stock item, prices it from the catalogue, shows the bill, and waits for an explicit confirm. It asks when rice or oil matches more than one row, and it does not pick a variety. It offers only catalogue substitutes, and only after the customer agrees. Paneer and anything else absent from the catalogue are declined, not guessed.

Ramesh must approve when a credit customer's outstanding balance plus this order exceeds the limit, or when the order is above Rs.3,000. Cash orders skip the credit check. Stock is reserved only after confirm, and only after that approval when approval is required. The queue shows the order, the reason, and a recommendation.

## State, cost, and what was cut

Orders, carts, stock changes, and the queue are in memory, loaded from `catalogue.json` and `customers.json` at startup. Section 9 allows that on a host that does not keep files between requests. It is not a shop system: a restart restores the original 39 rows and 7 customers, and every visitor of one process shares the same stock.

On Google's free tier, listed on 12 October 2026, standard Gemini 3.5 Flash Lite input and output are free of charge, so an order inside that quota costs Rs.0. The paid Standard rates on the same page are $0.30 per 1 million input tokens and $2.50 per 1 million output tokens. Billed token counts were not measured. See the README for the calculation template.

This repository was built in phased sessions. Those hours were not clocked, so this note does not claim the suggested 4-hour build or the 1 to 1.5-hour write-up.

## With another week

I would put orders, stock, and credit in a small hosted database so a restart and a second visitor do not wipe or share Ramesh's queue, and so the usage cap is enforced per account rather than per process. I would score live Gemini on the 12 scenarios, without treating today's mocked 12/12 as language accuracy, and I would log quota and parse failures separately from the customer sentence. I would also add the aliases that live calls still miss, such as an empty unit on Parle-G. The catalogue, the credit rule, and the Rs.3,000 rule would stay as they are.
