# TokenTally launch post — DRAFT, not published

Status: draft for the user's approval. Nothing posted yet. Repo not created, nothing pushed.

Rules for this post: only measured numbers, no user/sales/revenue claims, no invented quotes.

## X / Threads version

Claude, Cursor, OpenAI, Gemini — four bills, no total.

TokenTally reads your local usage exports and gives you one honest number: what you actually spent, by tool, by model, this month — plus a forecast and a budget warning before you blow it.

Free, open source, stdlib-only Python, local files only, no API keys, no sign-up.

## Longer version (README / Product Hunt style)

AI spend is scattered across tools and no provider shows you the total. TokenTally is the local-first spend ledger: import CSV or JSONL usage exports, or record rows by hand, and get totals by tool and model, a daily average, a month forecast, and a budget check (UNDER / AT_RISK / OVER).

- Demo (5 events, Nov 2026): 15,750 tokens, $0.21 priced, 1 unpriced row flagged, daily average $0.07, forecast $2.10, budget $2.50 = AT_RISK with $0.40 remaining
- Unpriced rows are counted and shown, never silently dropped; bad rows are reported line by line
- Forecasts say when the sample is thin (under 3 days = low confidence)

Measured, not estimated: 44 unit tests, all passing. No network, no keys, no paid API.
