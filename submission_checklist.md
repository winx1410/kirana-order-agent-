# Submission checklist

Nothing here has been pushed or deployed. The public link and the demo recording do not exist yet.

## Section 8 deliverables

| # | Deliverable | Status |
|---|---|---|
| 1 | Public app, kept up for at least two weeks after submission | Not done. Streamlit Cloud steps are in the README. No URL yet. |
| 2 | GitHub repo with run and deploy instructions, and no secrets | Remote exists: https://github.com/winx1410/kirana-order-agent-. Local branch `cursor/kirana-order-agent` has the app, tests, and this write-up. It is not pushed. `.env` is gitignored and untracked. |
| 3 | One-page design note | Written: `design_note.md`. Export or print it to PDF when you submit. |
| 4 | 3–5 minute demo: clean order, ambiguous order, escalation | Script only: `demo_script.md`. You still need to record it. |
| 5 | Eval set, automated checks, pass rate, two honest limitations | Done locally. `evals/scenarios.py`, `tests/test_evaluation.py`, `evaluation_report.md`. Mocked pass rate 12/12. |
| 6 | "With another week" | One paragraph at the end of `design_note.md`. |

## Section 9

| Rule | Status |
|---|---|
| Cut scope and say what was cut | Analytics questions ("what's running low?", "who owes more than Rs.2,000?") are not built. Said in the design note. |
| Approximate cost of one order | Free tier: Rs.0 while Google's quota holds. Paid Standard rates are verified. Token use was not measured. Formula is in the README. |
| Able to explain the design and walk through the code | Design note plus the module table in the README. |
| Public link | Not created yet. Streamlit Community Cloud is the intended host. |
| Keys in environment variables, never in the repo, plus a usage cap | `.env` and `.streamlit/secrets.toml` are gitignored. Cap is 10 per rolling minute and 400 per rolling 24 hours. |
| Simple state. Load Section 4 data at startup. No auth, WhatsApp, or voice | In-memory state. Catalogue and customers load from the repo directory. The owner page has no login, so public visitors can use the demo approval buttons. |

The assignment suggests about 4 hours of building and 1 to 1.5 hours of evals and write-up. This project was built across phased sessions. Those hours were not clocked, so this checklist does not claim that budget was met.

## Section 10

| They are looking for | Where it shows up |
|---|---|
| LLM judgement versus deterministic code | Gemini returns an intent only. Resolver and order engine own SKUs, prices, stock, credit, and confirmation. |
| Ask, act, never invent, escalate | Ambiguous rice and oil ask. Unique in-stock items are priced. Unknown items are declined. Credit and orders over Rs.3,000 wait for Ramesh. Substitutes wait for consent. |
| Measure, and be honest about failures | 12/12 is the mocked business-logic score. The report says it is not Gemini accuracy, and it records two limitations that are still true. |
| Prioritised pain points and trade-offs | Design note: messy orders, lost orders, stock, and credit were in scope. Analytics were cut. |
| Hosted app, a clear note, readable code | Note and code are local. The hosted app is the remaining step. |

## Before you submit

1. Read the README, design note, demo script, and evaluation report.
2. Approve a commit and push. Leave out `.env`, `.streamlit/secrets.toml`, and the assignment `.docx` unless you decide otherwise.
3. Deploy on Streamlit Community Cloud from `app.py`, with the secrets in the README.
4. Check `/` and `/owner_queue` on the public URL.
5. Record the demo from `demo_script.md`.
6. Keep the app deployed for two weeks.
7. Send the GitHub link, the public URL, the design-note PDF, the recording, and the eval report.
