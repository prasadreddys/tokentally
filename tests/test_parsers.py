import tempfile
import unittest
from pathlib import Path

from tokentally.parsers import (
    normalize_row, parse_csv, parse_import_file, parse_jsonl,
)


def _row(**kw):
    base = {"date": "2026-11-02", "tool": "claude", "model": "m",
            "input_tokens": 100, "output_tokens": 50, "cost_usd": "0.03"}
    base.update(kw)
    return base


class TestNormalize(unittest.TestCase):
    def test_valid_row(self):
        row = normalize_row(_row())
        self.assertEqual(row["date"], "2026-11-02")
        self.assertEqual(row["input_tokens"], 100)
        self.assertEqual(str(row["cost_usd"]), "0.03")

    def test_empty_cost_is_unpriced(self):
        self.assertIsNone(normalize_row(_row(cost_usd=""))["cost_usd"])
        self.assertIsNone(normalize_row(_row(cost_usd=None))["cost_usd"])

    def test_negative_tokens_rejected(self):
        with self.assertRaises(ValueError):
            normalize_row(_row(input_tokens=-1))
        with self.assertRaises(ValueError):
            normalize_row(_row(output_tokens="-5"))

    def test_negative_cost_rejected(self):
        with self.assertRaises(ValueError):
            normalize_row(_row(cost_usd="-0.01"))

    def test_non_numeric_cost_rejected(self):
        with self.assertRaises(ValueError):
            normalize_row(_row(cost_usd="free"))

    def test_bad_date_rejected(self):
        for bad in ("2026-13-01", "02/11/2026", "2026-11-2", "", None):
            with self.assertRaises(ValueError, msg=bad):
                normalize_row(_row(date=bad))

    def test_missing_tool_or_model_rejected(self):
        with self.assertRaises(ValueError):
            normalize_row(_row(tool="  "))
        with self.assertRaises(ValueError):
            normalize_row(_row(model=None))

    def test_at_overrides_date(self):
        row = normalize_row(_row(date="2026-01-01"), at="2026-11-10T09:30:00")
        self.assertEqual(row["date"], "2026-11-10")

    def test_bad_at_rejected(self):
        with self.assertRaises(ValueError):
            normalize_row(_row(), at="yesterday")


class TestCsvImport(unittest.TestCase):
    def _write(self, text):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
        tmp.write(text); tmp.close()
        return tmp.name

    def test_good_file(self):
        path = self._write(
            "date,tool,model,input_tokens,output_tokens,cost_usd\n"
            "2026-11-02,claude,m,100,50,0.03\n"
            "2026-11-03,cursor,m,200,100,\n")
        rows, errors = parse_csv(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(errors, [])
        self.assertIsNone(rows[1]["cost_usd"])

    def test_bad_rows_counted_and_reported(self):
        path = self._write(
            "date,tool,model,input_tokens,output_tokens,cost_usd\n"
            "2026-11-02,claude,m,100,50,0.03\n"
            "bad-date,claude,m,100,50,0.03\n"
            "2026-11-03,claude,m,-1,50,0.03\n"
            "2026-11-04,claude,m,100,50,abc\n")
        rows, errors = parse_csv(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual([ln for ln, _ in errors], [3, 4, 5])

    def test_bad_header_rejected(self):
        path = self._write("date,tool,model\n2026-11-02,claude,m\n")
        with self.assertRaises(ValueError):
            parse_csv(path)

    def test_tool_override(self):
        path = self._write(
            "date,tool,model,input_tokens,output_tokens,cost_usd\n"
            "2026-11-02,claude,m,100,50,0.03\n")
        rows, _ = parse_csv(path, tool_override="other")
        self.assertEqual(rows[0]["tool"], "other")


class TestJsonlImport(unittest.TestCase):
    def _write(self, text):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        tmp.write(text); tmp.close()
        return tmp.name

    def test_good_file(self):
        path = self._write(
            '{"date": "2026-11-02", "tool": "claude", "model": "m", '
            '"input_tokens": 100, "output_tokens": 50, "cost_usd": "0.03"}\n')
        rows, errors = parse_jsonl(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(errors, [])

    def test_bad_rows_reported(self):
        path = self._write(
            '{"date": "2026-11-02", "tool": "claude", "model": "m", '
            '"input_tokens": 100, "output_tokens": 50, "cost_usd": "0.03"}\n'
            'not json\n'
            '{"date": "2026-11-02", "tool": "claude", "model": "m", '
            '"input_tokens": -1, "output_tokens": 50}\n')
        rows, errors = parse_jsonl(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0][0], 2)

    def test_unsupported_format(self):
        with self.assertRaises(ValueError):
            parse_import_file("usage.txt")


if __name__ == "__main__":
    unittest.main()
