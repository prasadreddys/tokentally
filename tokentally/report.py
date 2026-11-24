"""Period reporting: totals, breakdowns by tool/model, daily average."""
from __future__ import annotations

import calendar
from decimal import Decimal

from .parsers import parse_date


def days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def period_bounds(period):
    """'YYYY-MM' -> (first_date, last_date, year, month, days_in_month)."""
    parts = str(period).split("-")
    if len(parts) != 2:
        raise ValueError(f"period must be YYYY-MM, got {period!r}")
    try:
        year, month = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError(f"period must be YYYY-MM, got {period!r}") from exc
    if not (1 <= month <= 12) or year < 1:
        raise ValueError(f"period must be YYYY-MM, got {period!r}")
    first = f"{year:04d}-{month:02d}-01"
    last = f"{year:04d}-{month:02d}-{days_in_month(year, month):02d}"
    return first, last, year, month, days_in_month(year, month)


def _empty_breakdown():
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            "cost_usd": Decimal("0"), "events": 0, "unpriced_events": 0}


def compute_report(rows, period):
    """Aggregate rows (already loaded) for one YYYY-MM period."""
    first, last, year, month, dim = period_bounds(period)
    selected = [r for r in rows if first <= r["date"] <= last]
    total = _empty_breakdown()
    by_tool, by_model = {}, {}
    days_with_events = set()
    for row in selected:
        days_with_events.add(row["date"])
        total["input_tokens"] += row["input_tokens"]
        total["output_tokens"] += row["output_tokens"]
        total["events"] += 1
        if row["cost_usd"] is None:
            total["unpriced_events"] += 1
        else:
            total["cost_usd"] += row["cost_usd"]
        for table, key in ((by_tool, row["tool"]), (by_model, row["model"])):
            entry = table.setdefault(key, _empty_breakdown())
            entry["input_tokens"] += row["input_tokens"]
            entry["output_tokens"] += row["output_tokens"]
            entry["events"] += 1
            if row["cost_usd"] is None:
                entry["unpriced_events"] += 1
            else:
                entry["cost_usd"] += row["cost_usd"]
    total["total_tokens"] = total["input_tokens"] + total["output_tokens"]
    for table in (by_tool, by_model):
        for entry in table.values():
            entry["total_tokens"] = entry["input_tokens"] + entry["output_tokens"]
    days = len(days_with_events)
    daily_avg = (total["cost_usd"] / days) if days else Decimal("0")
    return {
        "period": period,
        "events": total["events"],
        "input_tokens": total["input_tokens"],
        "output_tokens": total["output_tokens"],
        "total_tokens": total["total_tokens"],
        "priced_cost_usd": total["cost_usd"],
        "unpriced_events": total["unpriced_events"],
        "days_with_events": days,
        "days_in_period": dim,
        "daily_average_cost_usd": daily_avg,
        "by_tool": by_tool,
        "by_model": by_model,
    }
