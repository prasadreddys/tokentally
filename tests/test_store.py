import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from tokentally.store import Store


class TestStore(unittest.TestCase):
    def test_record_validation(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(d)
            row = store.record("claude", "sonnet", 100, 50, cost_usd=Decimal("0.03"),
                               at="2026-11-02")
            self.assertEqual(row["date"], "2026-11-02")
            self.assertEqual(len(store.load_rows()), 1)
            with self.assertRaises(ValueError):
                store.record("claude", "sonnet", -1, 50)
            with self.assertRaises(ValueError):
                store.record("claude", "sonnet", 100, 50, cost_usd=Decimal("-1"))
            with self.assertRaises(ValueError):
                store.record("claude", "sonnet", 100, 50, at="not-a-date")

    def test_unpriced_row_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(d)
            store.record("gemini", "flash", 10, 5)
            rows = store.load_rows()
            self.assertIsNone(rows[0]["cost_usd"])

    def test_budget_set_and_get(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(d)
            self.assertIsNone(store.get_budget())
            store.set_budget(Decimal("25.50"))
            self.assertEqual(store.get_budget(), Decimal("25.50"))
            with self.assertRaises(ValueError):
                store.set_budget(Decimal("-1"))

    def test_rows_persist_across_instances(self):
        with tempfile.TemporaryDirectory() as d:
            Store(d).record("claude", "sonnet", 1, 1, at="2026-11-02")
            self.assertEqual(len(Store(d).load_rows()), 1)


if __name__ == "__main__":
    unittest.main()
