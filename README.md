# TokenTally v1

Local-first AI spend ledger. Solo devs pay for Claude, Cursor, OpenAI,
Gemini and more and have no single honest total. TokenTally reads local
usage exports and manual records, totals spend by tool and model,
forecasts the month, and warns when a budget is about to be blown —
all offline. **No API keys, no network, no paid services. Stdlib-only
Python 3.12 — no dependencies to install. Free / $0.**

## Quick start

```bash
cd tokentally
python3 -m unittest discover -s tests -v   # unit suite
./run_tests.sh                              # unit suite + demo e2e

# 1. Templates:
python3 -m tokentally init --dir ./my-usage

# 2. Import a local export (or record one row by hand):
python3 -m tokentally import --store ./my-store --file ./my-usage/usage.csv
python3 -m tokentally record --store ./my-store --tool claude \
  --model claude-sonnet-4 --input 1000 --output 500 --cost 0.03 \
  --at 2026-11-02

# 3. Report, forecast, budget:
python3 -m tokentally report --store ./my-store --period 2026-11
python3 -m tokentally forecast --store ./my-store --period 2026-11
python3 -m tokentally budget --store ./my-store --set 25.00
python3 -m tokentally budget --store ./my-store --check --period 2026-11
```

## Import formats (exactly two)

**CSV** — header must be exactly:
`date,tool,model,input_tokens,output_tokens,cost_usd`
`date` is `YYYY-MM-DD`. `cost_usd` may be empty (the row is then
*unpriced* — counted, never billed). `--tool` overrides the tool column.

**JSONL** — one JSON object per line, same field names. `cost_usd` may
be a number, a string, or `""`/absent (unpriced).

Anything else (`.txt`, `.xlsx`, …) is rejected with a clear error.
No row is ever skipped silently: import prints `imported N rows,
skipped M` plus a per-line error for every bad row (bad date, negative
tokens, non-numeric cost).

## What a report means

- `events` — rows in the period; `total_tokens` = input + output.
- `priced_cost_usd` — sum of costs on priced rows only.
- `unpriced_events` — rows with no cost. They count in tokens/events
  but contribute $0 — the report never pretends it knows their price.
- `daily_average_cost_usd` — priced cost / days with events in the period.
- `by_tool` / `by_model` — the same totals broken down.

## Forecast

`daily average × days in the month`, where the daily average is priced
cost / days with events in the period. For the current month the
elapsed part of the month is used; for a past month the full period.
`low_confidence: true` when fewer than 3 days have data — the output
says so in plain text. A forecast is a projection, not a promise.

## Budget

`budget --set USD` stores a monthly budget (≥ 0) in the store.
`budget --check` compares the forecast (or the actual spend, when the
period is past) with the budget:

| Status | Meaning |
|---|---|
| `UNDER` | projected ≤ 80% of budget |
| `AT_RISK` | projected > 80% of budget but ≤ 100% |
| `OVER` | projected > budget |

`remaining_usd` is budget − projected (negative when OVER).
`--today YYYY-MM-DD` is a testing aid that pins "today" for the
forecast/budget commands so demos are reproducible.

## Money

All money is USD, `Decimal`, rounded half-up to cents for display.
Totals are exact Decimals internally; JSON output renders them as
numbers with two decimals.

## Layout

```
tokentally/
  tokentally/  __init__.py __main__.py cli.py store.py parsers.py report.py forecast.py
  tests/       stdlib unittest only
  examples/    usage.csv / usage.jsonl / expected-report.json (hand-computed)
  run_tests.sh
```

## Limitations (honest)

- TokenTally trusts the exports and rows you give it. It cannot verify
  that a provider's export is complete, and it cannot see spend that
  was never exported or recorded.
- Unpriced rows are excluded from cost totals and forecasts — if most
  rows are unpriced, the forecast understates spend. The report shows
  the unpriced count so this is visible.
- One writer at a time: the store is plain local files, no locking or
  multi-machine sync.
- No payments, no tax, no FX conversion — currency is a USD label.
- Prices are whatever the export says; TokenTally has no live price
  list and never fetches one.
