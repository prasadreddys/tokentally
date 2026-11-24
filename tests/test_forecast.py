import unittest
from datetime import date
from decimal import Decimal

from tokentally.forecast import budget_status, compute_forecast
from tokentally.parsers import normalize_row


def _rows():
    data = [
        ("2026-11-02", "claude", "sonnet", 1000, 500, "0.03"),
        ("2026-11-03", "claude", "sonnet", 2000, 1000, "0.06"),
        ("2026-11-03", "cursor", "gpt-5", 500, 250, "0.02"),
        ("2026-11-05", "openai", "gpt-4o", 3000, 1500, "0.10"),
        ("2026-11-05", "gemini", "flash", 4000, 2000, ""),
    ]
    return [normalize_row({"date": d, "tool": t, "model": m,
                           "input_tokens": i, "output_tokens": o,
                           "cost_usd": c}) for d, t, m, i, o, c in data]


class TestForecast(unittest.TestCase):
    def test_hand_computed_projection(self):
        # priced 0.21 over 3 days = 0.07/day; Nov has 30 days -> 2.10
        fc = compute_forecast(_rows(), "2026-11", today=date(2026, 11, 24))
        self.assertEqual(fc["daily_average_cost_usd"], Decimal("0.07"))
        self.assertEqual(fc["projected_month_total_usd"], Decimal("2.10"))
        self.assertEqual(fc["sample_days"], 3)
        self.assertTrue(fc["is_current_month"])
        self.assertEqual(fc["elapsed_days"], 24)

    def test_low_confidence_flag(self):
        one = _rows()[:1]
        fc = compute_forecast(one, "2026-11", today=date(2026, 11, 24))
        self.assertTrue(fc["low_confidence"])
        self.assertEqual(fc["sample_days"], 1)

    def test_three_days_not_low_confidence(self):
        fc = compute_forecast(_rows(), "2026-11", today=date(2026, 11, 24))
        self.assertFalse(fc["low_confidence"])

    def test_past_month_uses_full_period(self):
        fc = compute_forecast(_rows(), "2026-11", today=date(2026, 12, 5))
        self.assertFalse(fc["is_current_month"])
        self.assertEqual(fc["elapsed_days"], 30)
        self.assertEqual(fc["projected_month_total_usd"], Decimal("2.10"))

    def test_no_data_forecasts_zero(self):
        fc = compute_forecast([], "2026-11", today=date(2026, 11, 24))
        self.assertEqual(fc["projected_month_total_usd"], Decimal("0"))
        self.assertTrue(fc["low_confidence"])


class TestBudgetStatus(unittest.TestCase):
    def _fc(self, projected):
        return {"projected_month_total_usd": Decimal(str(projected))}

    def test_under(self):
        r = budget_status(self._fc("2.10"), Decimal("3.00"))
        self.assertEqual(r["status"], "UNDER")
        self.assertEqual(r["remaining_usd"], Decimal("0.90"))

    def test_at_risk_above_80_percent(self):
        # 2.10 / 2.50 = 84% -> AT_RISK
        r = budget_status(self._fc("2.10"), Decimal("2.50"))
        self.assertEqual(r["status"], "AT_RISK")

    def test_at_risk_boundary_80_percent_is_under(self):
        # exactly 80% is not > 80%, so UNDER
        r = budget_status(self._fc("2.00"), Decimal("2.50"))
        self.assertEqual(r["status"], "UNDER")

    def test_over(self):
        r = budget_status(self._fc("2.10"), Decimal("2.00"))
        self.assertEqual(r["status"], "OVER")
        self.assertEqual(r["remaining_usd"], Decimal("-0.10"))

    def test_no_budget(self):
        r = budget_status(self._fc("2.10"), None)
        self.assertIsNone(r["status"])


if __name__ == "__main__":
    unittest.main()
