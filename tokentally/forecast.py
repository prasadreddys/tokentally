"""Forecasting and budget checks.

Forecast: daily average cost = priced cost / days with events (within the
elapsed part of the period), projected month total = daily average * days
in the month. Sample is thin (low confidence) when fewer than 3 days
have events.
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from .report import compute_report, days_in_month, period_bounds


def _quant(value):
    return Decimal(value).quantize(Decimal("0.01"))


def compute_forecast(rows, period, today=None):
    """Forecast a YYYY-MM period. today: datetime.date, default real today."""
    today = today or date.today()
    first, last, year, month, dim = period_bounds(period)
    report = compute_report(rows, period)
    is_current = (today.year, today.month) == (year, month)
    if is_current:
        elapsed_days = today.day
    else:
        elapsed_days = dim
    sample_days = report["days_with_events"]
    if sample_days:
        daily_avg = report["priced_cost_usd"] / sample_days
    else:
        daily_avg = Decimal("0")
    projected = daily_avg * dim
    return {
        "period": period,
        "is_current_month": is_current,
        "elapsed_days": elapsed_days,
        "sample_days": sample_days,
        "low_confidence": sample_days < 3,
        "daily_average_cost_usd": daily_avg,
        "days_in_month": dim,
        "priced_cost_usd": report["priced_cost_usd"],
        "projected_month_total_usd": projected,
        "events": report["events"],
    }


def budget_status(forecast, budget):
    """UNDER / AT_RISK / OVER for a forecast (or actual) amount vs budget.

    AT_RISK: projected > 80% of budget but <= 100%.
    budget may be None (no budget set) -> status None.
    """
    if budget is None:
        return {"status": None, "remaining_usd": None, "budget_usd": None}
    projected = Decimal(str(forecast["projected_month_total_usd"]))
    budget = Decimal(str(budget))
    if projected > budget:
        status = "OVER"
    elif projected > budget * Decimal("0.8"):
        status = "AT_RISK"
    else:
        status = "UNDER"
    return {
        "status": status,
        "budget_usd": budget,
        "projected_usd": projected,
        "remaining_usd": budget - projected,
    }
