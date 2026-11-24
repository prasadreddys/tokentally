import unittest
from decimal import Decimal

from tokentally.parsers import normalize_row
from tokentally.report import compute_report, period_bounds


def _rows():
    data = [
        ("2026-11-02", "claude", "sonnet", 1000, 500, "0.03"),
        ("2026-11-03", "claude", "sonnet", 2000, 1000, "0.06"),
        ("2026-11-03", "cursor", "gpt-5", 500, 250, "0.02"),
        ("2026-11-05", "openai", "gpt-4o", 3000, 1500, "0.10"),
        ("2026-11-05", "gemini", "flash", 4000, 2000, ""),
        ("2026-10-31", "claude", "sonnet", 999, 999, "9.99"),
    ]
    return [normalize_row({"date": d, "tool": t, "model": m,
                           "input_tokens": i, "output_tokens": o,
                           "cost_usd": c}) for d, t, m, i, o, c in data]


class TestReport(unittest.TestCase):
    def test_totals(self):
        r = compute_report(_rows(), "2026-11")
        self.assertEqual(r["events"], 5)
        self.assertEqual(r["input_tokens"], 10500)
        self.assertEqual(r["output_tokens"], 5250)
        self.assertEqual(r["total_tokens"], 15750)
        self.assertEqual(r["priced_cost_usd"], Decimal("0.21"))
        self.assertEqual(r["unpriced_events"], 1)

    def test_period_filter_excludes_october(self):
        r = compute_report(_rows(), "2026-10")
        self.assertEqual(r["events"], 1)
        self.assertEqual(r["priced_cost_usd"], Decimal("9.99"))

    def test_breakdown_by_tool(self):
        r = compute_report(_rows(), "2026-11")
        self.assertEqual(r["by_tool"]["claude"]["events"], 2)
        self.assertEqual(r["by_tool"]["claude"]["cost_usd"], Decimal("0.09"))
        self.assertEqual(r["by_tool"]["gemini"]["unpriced_events"], 1)
        self.assertEqual(r["by_tool"]["gemini"]["cost_usd"], Decimal("0"))

    def test_breakdown_by_model(self):
        r = compute_report(_rows(), "2026-11")
        self.assertEqual(r["by_model"]["sonnet"]["total_tokens"], 4500)
        self.assertEqual(r["by_model"]["gpt-4o"]["cost_usd"], Decimal("0.10"))

    def test_daily_average_and_days(self):
        r = compute_report(_rows(), "2026-11")
        self.assertEqual(r["days_with_events"], 3)
        self.assertEqual(r["days_in_period"], 30)
        self.assertEqual(r["daily_average_cost_usd"], Decimal("0.07"))

    def test_empty_period(self):
        r = compute_report(_rows(), "2026-12")
        self.assertEqual(r["events"], 0)
        self.assertEqual(r["priced_cost_usd"], Decimal("0"))
        self.assertEqual(r["daily_average_cost_usd"], Decimal("0"))

    def test_bad_period(self):
        with self.assertRaises(ValueError):
            period_bounds("2026-13")
        with self.assertRaises(ValueError):
            period_bounds("november")


if __name__ == "__main__":
    unittest.main()
