# Demo script (3–5 minutes)

Record this yourself. This file is the script only. No recording is in the repository.

Use the customer dropdown on the order chat. Open Ramesh's queue from the sidebar page "owner queue". Prices on screen come from the catalogue. If the assistant says it has reached the message limit, stop and wait. Do not keep retrying.

## 0:00–0:25 — Introduction

Say: this is an order assistant for Ramesh's kirana. Gemini only reads the message. Python matches the catalogue, prices the bill, checks stock and credit, and decides when Ramesh has to approve.

## 0:25–1:20 — Clean order, Priya Nair (C006)

Select **C006 · Priya Nair**. She pays cash.

Send:

`1 litre Fortune oil and 5 Parle-G`

Show the bill: Fortune Sunflower Oil, 1 L and 5 Parle-G. Total **Rs.185**. The order is not placed yet. Fortune stock is still 60 and Parle-G is still 200.

Send:

`haan, confirm`

Show the confirmed order id. Say that stock is reserved only now.

## 1:20–2:25 — Ambiguous rice, Anita Sharma (C002)

Select **C002 · Anita Sharma**.

Send the original wording:

`bhaiya 2 kg sugar, 5 kg rice send kar do`

Show that 2 kg sugar is added, and that rice is still a question. The question must list loose Sona Masoori and boiled rice by the kg, and India Gate Basmati as 5 packs of 1 kg. Say that the assistant has not chosen a variety.

Send:

`Sona Masoori`

Show 2 kg sugar and 5 kg Sona Masoori. Total **Rs.402** (Rs.46 × 2 + Rs.62 × 5). Do not confirm unless you have time. Stock should stay unchanged until confirm.

## 2:25–3:25 — Credit escalation, Suresh Reddy (C001)

Select **C001 · Suresh Reddy**. Outstanding is Rs.4,800. Limit is Rs.5,000.

Send:

`Aashirvaad 5 kg atta, 2 kg toor dal, 1 litre Fortune oil aur 1 Tata Tea Gold bhej do`

Show the bill **Rs.880** and the warning that confirming sends it to Ramesh because the credit limit would be exceeded. Aashirvaad stock should still be 25.

Send:

`haan, confirm`

Show the message that the order is with Ramesh and is not confirmed.

## 3:25–4:10 — Ramesh approves

Open **owner queue**. Show Suresh's order, the reason "Customer credit limit exceeded", the recommendation, and the packing lines with prices.

Click **Approve** once.

Return to the order chat for C001 without typing a new message. The page should say Ramesh approved it. Say that this refresh did not call Gemini.

On the owner page, show the confirmed packing list: Aashirvaad Atta 5 kg, toor dal, Fortune oil, and Tata Tea Gold.

## 4:10–4:45 — How it is split, and what it does not do

Say: Gemini returns an intent. The resolver maps words to SKUs. The order engine computes money, stock, and credit. The agent asks, waits for consent, or escalates.

Say the two limits you will mention: the 12/12 score uses mocked language understanding, so it is not a live Gemini score. Orders live in this running app. A restart clears the queue and restores catalogue stock. A database, and a live evaluation of Gemini, are the next week of work.
