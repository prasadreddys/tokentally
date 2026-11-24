"""TokenTally CLI. Local only; all money USD, Decimal, half-up to cents."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation

from .forecast import budget_status, compute_forecast
from .parsers import parse_import_file
from .report import compute_report
from .store import Store


def _money(value):
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def _jsonable(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def _dump(obj):
    print(json.dumps(_jsonable(obj), indent=2, sort_keys=True))


def _current_period():
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def _dec_arg(text):
    try:
        value = Decimal(str(text))
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return value


def build_parser():
    parser = argparse.ArgumentParser(prog="tokentally", description="Local-first AI spend ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("record", help="record one usage row")
    p.add_argument("--store", default="./tokentally-store")
    p.add_argument("--tool", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--input", type=int, required=True, dest="input_tokens")
    p.add_argument("--output", type=int, required=True, dest="output_tokens")
    p.add_argument("--cost", type=_dec_arg, default=None)
    p.add_argument("--at", default=None, help="ISO-8601 timestamp or date")
    p.add_argument("--source", default="manual")

    p = sub.add_parser("import", help="import a usage .csv or .jsonl file")
    p.add_argument("--store", default="./tokentally-store")
    p.add_argument("--file", required=True)
    p.add_argument("--tool", default=None)

    p = sub.add_parser("report", help="totals for a period")
    p.add_argument("--store", default="./tokentally-store")
    p.add_argument("--period", default=None)
    p.add_argument("--tool", default=None)

    p = sub.add_parser("forecast", help="month forecast from a period")
    p.add_argument("--store", default="./tokentally-store")
    p.add_argument("--period", default=None)
    p.add_argument("--today", default=None, help="YYYY-MM-DD, testing aid")

    p = sub.add_parser("budget", help="set or check the monthly budget")
    p.add_argument("--store", default="./tokentally-store")
    p.add_argument("--set", type=_dec_arg, default=None, dest="set_amount")
    p.add_argument("--check", action="store_true")
    p.add_argument("--period", default=None)
    p.add_argument("--today", default=None, help="YYYY-MM-DD, testing aid")

    p = sub.add_parser("init", help="write sample import templates")
    p.add_argument("--dir", required=True)
    return parser


def _filter_tool(report, tool):
    if tool is None:
        return report
    entry = report["by_tool"].get(tool)
    if entry is None:
        return {"period": report["period"], "tool": tool, "events": 0,
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                "priced_cost_usd": Decimal("0"), "unpriced_events": 0,
                "days_with_events": 0, "days_in_period": report["days_in_period"],
                "daily_average_cost_usd": Decimal("0"), "by_tool": {}, "by_model": {}}
    out = dict(report)
    out["tool"] = tool
    out["events"] = entry["events"]
    out["input_tokens"] = entry["input_tokens"]
    out["output_tokens"] = entry["output_tokens"]
    out["total_tokens"] = entry["total_tokens"]
    out["priced_cost_usd"] = entry["cost_usd"]
    out["unpriced_events"] = entry["unpriced_events"]
    out["daily_average_cost_usd"] = (
        entry["cost_usd"] / out["days_with_events"] if out["days_with_events"] else Decimal("0")
    )
    return out


def _print_report(report):
    print(f"Period: {report['period']}  events: {report['events']}  "
          f"tokens: {report['total_tokens']} (in {report['input_tokens']}, "
          f"out {report['output_tokens']})")
    print(f"Priced cost: ${_money(report['priced_cost_usd']):.2f}  "
          f"unpriced events: {report['unpriced_events']}  "
          f"days with events: {report['days_with_events']}/{report['days_in_period']}  "
          f"daily avg: ${_money(report['daily_average_cost_usd']):.2f}")
    for tool, entry in sorted(report["by_tool"].items()):
        cost = "unpriced" if entry["cost_usd"] == 0 and entry["unpriced_events"] else f"${_money(entry['cost_usd']):.2f}"
        print(f"  {tool}: {entry['events']} events, {entry['total_tokens']} tokens, {cost}")
    _dump(report)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _run(args):
    if args.command == "init":
        from pathlib import Path
        out = Path(args.dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "usage.csv").write_text(
            "date,tool,model,input_tokens,output_tokens,cost_usd\n"
            "2026-11-02,claude,claude-sonnet-4,1000,500,0.03\n"
            "2026-11-03,claude,claude-sonnet-4,2000,1000,0.06\n",
            encoding="utf-8")
        (out / "usage.jsonl").write_text(
            '{"date": "2026-11-02", "tool": "claude", "model": "claude-sonnet-4", '
            '"input_tokens": 1000, "output_tokens": 500, "cost_usd": "0.03"}\n'
            '{"date": "2026-11-03", "tool": "claude", "model": "claude-sonnet-4", '
            '"input_tokens": 2000, "output_tokens": 1000, "cost_usd": "0.06"}\n',
            encoding="utf-8")
        print(f"wrote {out / 'usage.csv'} and {out / 'usage.jsonl'}")
        return 0

    store = Store(args.store)

    if args.command == "record":
        row = store.record(args.tool, args.model, args.input_tokens,
                           args.output_tokens, cost_usd=args.cost,
                           at=args.at, source=args.source)
        print(f"recorded {row['id']}  {row['date']} {row['tool']}/{row['model']} "
              f"in={row['input_tokens']} out={row['output_tokens']} "
              f"cost={row['cost_usd'] if row['cost_usd'] is not None else 'unpriced'}")
        return 0

    if args.command == "import":
        rows, errors = parse_import_file(args.file, args.tool)
        store.add_rows(rows)
        print(f"imported {len(rows)} rows, skipped {len(errors)}")
        for line_no, msg in errors:
            print(f"  line {line_no}: {msg}")
        return 0

    if args.command == "report":
        period = args.period or _current_period()
        report = compute_report(store.load_rows(), period)
        report = _filter_tool(report, args.tool)
        _print_report(report)
        return 0

    if args.command == "forecast":
        period = args.period or _current_period()
        today = None
        if args.today:
            from datetime import date as _date
            today = _date.fromisoformat(args.today)
        fc = compute_forecast(store.load_rows(), period, today=today)
        print(f"Period: {period}  sample days: {fc['sample_days']}  "
              f"daily avg: ${_money(fc['daily_average_cost_usd']):.2f}  "
              f"projected month total: ${_money(fc['projected_month_total_usd']):.2f}")
        if fc["low_confidence"]:
            print("LOW CONFIDENCE: fewer than 3 days of data — forecast is thin.")
        _dump(fc)
        return 0

    if args.command == "budget":
        if args.set_amount is not None:
            amount = store.set_budget(args.set_amount)
            print(f"monthly budget set to ${_money(amount):.2f}")
            return 0
        if args.check:
            period = args.period or _current_period()
            rows = store.load_rows()
            today = date.today()
            if args.today:
                today = date.fromisoformat(args.today)
            fc = compute_forecast(rows, period, today=today)
            budget = store.get_budget()
            if budget is None:
                print("no budget set — use `budget --set USD` first")
                return 0
            # Past period: compare actual spend, not the forecast.
            from .report import period_bounds
            _, last, _, _, _ = period_bounds(period)
            if last < today.isoformat():
                fc = dict(fc, projected_month_total_usd=fc["priced_cost_usd"])
            result = budget_status(fc, budget)
            result["period"] = period
            print(f"Budget: ${_money(budget):.2f}  projected/actual: "
                  f"${_money(result['projected_usd']):.2f}  "
                  f"remaining: ${_money(result['remaining_usd']):.2f}  status: {result['status']}")
            _dump(result)
            return 0
        parser = build_parser()
        parser.error("budget needs --set USD or --check")
        return 2

    return 2
