# Evaluation report

Phase F checks order outcomes with mocked language understanding. This run did not call Gemini.

## Methodology

Each case sends the original customer wording into `KiranaAgent.handle`. The structured intent that would have come from Gemini is supplied by the test, then checked with `nlu.validate_payload`. Prices, stock, credit, substitutions, and confirmation still go through `resolver.py` and `order_engine.py`.

Assertions look at the cart, bill, clarification set, substitution consent, order status, approval reason, recommendation, outstanding balance, and stock. Where a case states both a cart and a bill, the test recomputes the bill as catalogue unit price times quantity and requires the stated amount to match that product. It does not call `calculate_total` for the expected amount. State is reset before every case. A case fails if any turn's outcome differs from the expected values.

This pass rate is not a live Gemini score. Live calls are a separate path, gated by `NLU_LIVE_TEST=1`, and were not run here.

## Dataset

Twelve cases. Eight use the Section 6 wording. Four add failure modes. Multi-turn cases include the follow-up in the same case.

| Case | What is checked |
|---|---|
| official-1-rice-clarification | `bhaiya 2 kg sugar, 5 kg rice send kar do` keeps sugar (SKU-001, 2 kg) and asks among SKU-002, SKU-003, and SKU-004. The question separates loose rice, sold per kg, from India Gate Basmati sold as 5 packs of 1 kg. Choosing Sona Masoori yields 5 kg and a bill of Rs.402. Stock is unchanged. |
| official-2-usual-order | `usual order bhejo` for Lakshmi Devi lists her five usual lines and a bill of Rs.335, and waits for confirmation. |
| official-3-clean-confirm | `1 litre Fortune oil and 5 Parle-G` bills Rs.185. `haan, confirm` confirms the order and moves Fortune oil 60 to 59 and Parle-G 200 to 195. |
| official-4-surf-consent | `2 Surf Excel 1kg` leaves the cart empty and offers only Tide Plus and Ariel. Tide is added only after an accept-substitution turn. Surf stock stays 0 and Tide stock stays 30 until a later confirm. |
| official-5-credit-approval | Suresh's atta, toor, Fortune oil, and Tata Tea Gold bill is Rs.880 with reason "Customer credit limit exceeded". Confirm queues it without reserving stock or changing the Rs.4800 outstanding balance. Owner approval confirms the same order, sets the agent status to confirmed without a new customer message, sets atta stock to 24, and sets outstanding to Rs.5680. The queue stores a recommendation. |
| official-6-chini-tel | `chini 2 kilo aur tel ek litre` resolves sugar and asks among the three in-stock oils. No oil brand is chosen. |
| official-7-paneer | `1 kg paneer aur 2 Lay's` marks paneer unsupported and bills 2 Lay's at Rs.40. |
| official-8-modify-order | A summary of 5 kg Sona Masoori and 2 Parle-G (Rs.330) then `rice 10 kg kar do, biscuits cancel` leaves 10 kg rice at Rs.620. Parle-G stock is not touched. |
| extra-duplicate-confirm | Confirming the Rs.185 order twice keeps one order id and deducts Fortune oil and Parle-G once. |
| extra-reject-substitution | Declining a Surf Excel substitute adds neither Tide nor Ariel and does not change their stock. |
| extra-maggi-shortage | 4 Maggi, with only 3 in stock, offers Yippee and does not add it until consent. Confirm then deducts 4 Yippee and leaves Maggi at 3. Bill is Rs.56. |
| extra-cash-over-3000 | 50 kg Sona Masoori is Rs.3100. Confirm waits for Ramesh because the order exceeds Rs.3000. Rice stock stays 150. Anita's outstanding balance stays 0. |

## Scenario 1 bill

Rs.402 is the correct catalogue bill. It was not adjusted to match a test.

| Line | Catalogue row | Unit price | Quantity | Amount |
|---|---|---|---|---|
| Sugar (loose) | SKU-001, sold per kg | Rs.46 | 2 kg | Rs.92 |
| Sona Masoori Rice (loose) | SKU-002, sold per kg | Rs.62 | 5 kg | Rs.310 |
| Total | | | | Rs.402 |

`2 × 46 + 5 × 62 = 402`. The evaluation now fails if that stated total disagrees with those catalogue prices. Catalogue prices were not changed.

## Results

Observed outcomes matched the expected outcomes above for all 12 cases. There were no failed cases.

Phase F evaluation: **12 passed, 0 failed**. Pass rate: **12/12 = 100%**.

Full suite, including earlier engine, resolver, NLU, agent, and Streamlit tests: **97 passed, 1 skipped, 0 failed**. The skip is `test_live_gemini_smoke_clean_order`, which runs only when `NLU_LIVE_TEST=1` and an API key are set. That flag was unset. Gemini was not called. The latest added test checks that root-level Cloud settings are read from environment variables, using a fake key.

## Mocked results and live observations

The 100% figure is the mocked-NLU business-logic score. It does not measure how often Gemini extracts the right intent from Hindi-English text.

Earlier live calls, not repeated in this phase, showed separate behaviour: Parle-G sometimes came back with quantity 5 and an empty unit; a Google quota error and the local cap produced the same customer sentence; sending `thinking_budget=0` to `gemini-3.5-flash-lite` returned HTTP 400 until that setting was removed. Those observations are not part of the 12/12 score.

## Fixes in this review

The customer chat now reads the order record on each render and copies that status before drawing the page. Approving shows "Ramesh approved this order. It is confirmed." Rejecting shows "Ramesh rejected this order. Nothing was reserved." Neither path sends a message to Gemini. A later shopping message after a rejection starts a new cart and leaves the rejected order closed.

For mixed rice matches, the question now says which lines are loose and sold per kg, and which are packs. For this order it offers 5 kg Sona Masoori, 5 kg boiled rice, and 5 packs of India Gate Basmati, 1 kg, and it says that none has been chosen.

## Limitations

Both notes below are still true. They are not failed evaluation cases.

**The 100% score does not measure Gemini.** Every case in this run used a scripted intent. Earlier live calls, not repeated here, sometimes returned Parle-G with quantity 5 and an empty unit, and a Google quota error used the same customer sentence as the local usage cap. Those observations stay outside the 12/12 score.

**Orders live only in this Streamlit process.** Restarting the app reloads the catalogue and drops the queue, stock changes, and outstanding updates. A new browser session also drops an unconfirmed cart from the screen, because the cart is stored on the session. Confirmed stock and credit are not written to a database.

## Production changes in this review

`agent.py` now builds the rice question from each candidate's unit, copies the order status when asked, and starts a fresh cart after a rejected order when the customer names a new order. `app.py` calls that status copy on every render, including reruns that do not submit a chat message. Catalogue rows, customer rows, prices, credit rules, and the Rs.3000 rule were not changed.
