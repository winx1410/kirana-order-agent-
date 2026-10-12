# Kirana order-taking agent

An order assistant for Ramesh's neighbourhood kirana. Customers type the way they speak, including Hindi and English in the same message. The assistant turns that into a catalogue order, a bill, and either a confirmed order or an item on Ramesh's approval queue.

Gemini 3.5 Flash Lite only reads the message. Python matches products, prices the bill, checks stock and credit, and decides when to ask, when to wait for consent, and when to hand the order to Ramesh.

This is a take-home assignment build. It is not a production shop system.

## Problem

Orders arrive as texts such as "bhaiya, 2 kg sugar, 5 kg rice, send kar do". The brand, the pack size, and the unit are often missing. Stock and udhaar (credit) are easy to get wrong if they are decided while packing. This assistant keeps one version of the order and applies the shop's rules before anything is reserved.

## Features

- Maps messy wording, including chini, tel, and "the usual", onto the fixed 39-item catalogue.
- Asks once when several products match, and names loose rice sold per kg separately from 1 kg packs.
- Prices every line from the catalogue. The model never supplies a price.
- Offers only the owner's approved substitutes, and only after the customer agrees.
- Reserves stock only when the customer confirms, and only after Ramesh approves when approval is required.
- Sends credit-limit breaches and orders above Rs.3,000 to Ramesh, with the reason and a recommendation.
- Customer chat and owner queue share the same in-memory orders for one running app.

## Architecture

| Piece | Responsibility |
|---|---|
| `app.py` | Customer chat. Calls Gemini only when a new message is submitted. |
| `pages/owner_queue.py` | Ramesh's queue and confirmed packing lists. Does not call Gemini. |
| `nlu.py` | Gemini structured intent. Validates JSON. Enforces the usage cap. |
| `resolver.py` | Catalogue match, units, ambiguity, and approved substitutes. |
| `agent.py` | Conversation: cart, questions, consent, confirm, and cancel. |
| `order_engine.py` | Totals, stock, credit, order ids, and the approval queue. |
| `catalogue.json`, `customers.json` | The 39 products and 7 customers from the assignment. Do not edit them. |

## Run it locally

Python 3.9 or newer. This copy was run with Python 3.9.6.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .env
```

Edit `.env` and set `GEMINI_API_KEY`. Do not commit that file.

```bash
streamlit run app.py
```

- Customer chat: [http://localhost:8501](http://localhost:8501)
- Owner queue: use the sidebar page **owner queue**, or open [http://localhost:8501/owner_queue](http://localhost:8501/owner_queue)

Choose a customer in the sidebar. Priya Nair (C006) is a cash customer. Suresh Reddy (C001) is already near his credit limit.

### Gemini settings

| Variable | Purpose | Default in code |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio key. Required for live chat. | none |
| `GEMINI_MODEL` | Model id | `gemini-3.5-flash-lite` |
| `GEMINI_RPM_LIMIT` | Max calls in a rolling minute, shared by this process | `10` |
| `GEMINI_DAILY_LIMIT` | Max calls in a rolling 24 hours, shared by this process | `400` |

The app reads these from the environment or from a `.env` file in the project folder. On Streamlit Community Cloud, put the same keys in the app's Secrets box. See Deployment below.

A missing key, a quota error, or a busy model leaves the cart unchanged. The app does not retry a 429.

### Example

As Anita Sharma (C002):

```text
bhaiya 2 kg sugar, 5 kg rice send kar do
```

Sugar is added. Rice stays a question: loose Sona Masoori and boiled rice by the kg, or 5 packs of India Gate Basmati, 1 kg.

```text
Sona Masoori
```

The bill is Rs.402, from Rs.46/kg sugar and Rs.62/kg Sona Masoori. Nothing is reserved until she confirms.

## Business rules

- Prices, SKUs, and discounts come only from the catalogue.
- An item that is not stocked is declined. The assistant does not guess a neighbour.
- Stock is reserved on confirm, not when the message is parsed.
- Cash customers are not credit-checked.
- If outstanding balance plus this order exceeds a credit limit, Ramesh must approve.
- Any order above Rs.3,000 needs Ramesh's approval.
- Substitutes come only from that product's approved list, and only with consent.
- The queue shows the order, the flag reason, and the agent's recommendation.

## Evaluation

`evals/scenarios.py` holds 12 cases: the 8 starter messages plus duplicate confirmation, a declined substitute, a Maggi shortage, and a cash order over Rs.3,000. `tests/test_evaluation.py` checks the cart, the catalogue bill, whether a question was asked, consent, status, the approval reason, and stock. Language understanding is mocked, so this does not spend API quota and does not measure Gemini.

Latest mocked run: **12 passed, 0 failed. Pass rate 12/12 = 100%.** That score is not live Gemini accuracy. Details, including two real limitations, are in `evaluation_report.md`.

```bash
env -u NLU_LIVE_TEST python -m pytest -q
```

The live smoke test stays skipped unless `NLU_LIVE_TEST=1` and a key are set. Leave it unset for a normal run.

## Cost and rate limits

Checked on 12 October 2026 against [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) for `gemini-3.5-flash-lite`, Standard tier:

| | Free tier | Paid tier |
|---|---|---|
| Input | Free of charge | $0.30 per 1 million tokens |
| Output, including thinking tokens | Free of charge | $2.50 per 1 million tokens |

Currency is US dollars. No exchange rate is applied here.

Inside Google's free-tier quota, a typical order costs **Rs.0**. This project does not log billed token counts, so there is no measured dollar cost from a live call.

Each customer message is one request. A 2–3 message order is 2–3 requests. Confirming with Ramesh does not call Gemini. Rerunning the page does not call Gemini.

What we can count locally, which is not the tokenizer and not a bill:

- System instruction: 896 characters
- Response schema: 747 characters
- Three sample user prompts (a clean order, a rice choice, and "haan, confirm"): 79, 314, and 188 characters

A rough assumption of 4 characters per token puts those three inputs, including the system instruction and schema, near 1,400 input tokens together. Output is capped at 512 tokens per call and was not measured.

**Illustrative paid-tier cost, not a measured bill.** Using the rates above and the assumptions of 1,400 input tokens and 300 output tokens:

`(1,400 / 1,000,000) × $0.30 + (300 / 1,000,000) × $2.50 = $0.00117`

Actual billed tokens have not been measured. On the free tier the same order is Rs.0 while the quota holds.

```text
paid_usd = (input_tokens / 1_000_000) * 0.30 + (output_tokens / 1_000_000) * 2.50
```

The local cap is 10 requests per rolling minute and 400 per rolling 24 hours. It is stored in this process only. A restart clears it. Every session on that process shares it. It does not override Google's quota. An HTTP 429 still consumes a local slot, because the slot is taken before the request, and the app does not retry.

Earlier, this key's dashboard showed 15 requests per minute and 500 per day for Gemini 3.5 Flash Lite. That dashboard was not re-opened for this write-up.

## Deployment

Not deployed yet. There is no public URL.

Streamlit Community Cloud can host it after the GitHub branch is pushed.

1. Push the project. Do not push `.env` or `.streamlit/secrets.toml`.
2. In [Streamlit Community Cloud](https://share.streamlit.io), create an app from this repository.
3. Main file: `app.py`. The owner page is `pages/owner_queue.py`.
4. In the app's Secrets, paste root-level keys. Streamlit copies those into environment variables when the server starts. `nlu.py` reads the environment. It does not open a `secrets.toml` from this repository, and nested tables are not copied into environment variables.

```toml
GEMINI_API_KEY = "your-key"
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_RPM_LIMIT = "10"
GEMINI_DAILY_LIMIT = "400"
```

5. Open the app URL for the customer chat. Open `<app-url>/owner_queue` for Ramesh. There is no login. Anyone with the link can approve or reject orders, because the assignment excludes authentication.
6. Leave the app deployed for at least two weeks after submission. Cloud may sleep and then restart. A restart reloads the catalogue and clears orders, stock changes, and the queue.

Catalogue and customer files are read from the repository directory. The code does not use a machine-specific absolute path.

Pinned packages in `requirements.txt`: `streamlit==1.50.0`, `google-genai==1.47.0`, `pytest==8.4.2`.

## Limitations

- The owner queue has no login. The assignment excludes authentication, so anyone with the public link can approve or reject demo orders.
- Mocked evaluation does not measure Gemini. A live call has returned Parle-G with an empty unit, and a Google quota error uses the same customer sentence as the local cap.
- Orders, stock, and credit changes exist only in the running process. They are shared by everyone using that process, and they disappear on restart.
- The usage cap has the same process-local limit.
- Shop questions such as "what is running low?" are not built.

## Links

- GitHub remote: https://github.com/winx1410/kirana-order-agent-
- Branch with this work: `cursor/kirana-order-agent`. It has not been pushed as part of this preparation.
- Public app: not deployed yet.

Design note: `design_note.md`. Demo script, for you to record: `demo_script.md`. Submission checklist: `submission_checklist.md`.
