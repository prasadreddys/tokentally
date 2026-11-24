import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path

from tokentally.cli import main

BASE = Path(__file__).resolve().parents[1]
EXAMPLES = BASE / "examples"


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def _json_tail(output):
    return json.loads(output[output.index("{"):])  # first JSON object onward


class TestCliE2E(unittest.TestCase):
    def test_import_csv_report_forecast_budget_match_expected(self):
        expected = json.loads((EXAMPLES / "expected-report.json").read_text())
        with tempfile.TemporaryDirectory() as d:
            store = str(Path(d) / "store")
            code, out = _run(["import", "--store", store,
                              "--file", str(EXAMPLES / "usage.csv")])
            self.assertEqual(code, 0)
            self.assertIn("imported 5 rows, skipped 0", out)

            code, out = _run(["report", "--store", store, "--period", "2026-11"])
            self.assertEqual(code, 0)
            report = _json_tail(out)
            self.assertEqual(report["events"], expected["events"])
            self.assertEqual(report["input_tokens"], expected["input_tokens"])
            self.assertEqual(report["output_tokens"], expected["output_tokens"])
            self.assertEqual(report["total_tokens"], expected["total_tokens"])
            self.assertEqual(report["priced_cost_usd"], expected["priced_cost_usd"])
            self.assertEqual(report["unpriced_events"], expected["unpriced_events"])
            self.assertEqual(report["days_with_events"], expected["days_with_events"])
            for tool, exp in expected["by_tool"].items():
                got = report["by_tool"][tool]
                self.assertEqual(got["events"], exp["events"])
                self.assertEqual(got["input_tokens"], exp["input_tokens"])
                self.assertEqual(got["cost_usd"], exp["cost_usd"])

            code, out = _run(["forecast", "--store", store, "--period", "2026-11",
                              "--today", "2026-11-24"])
            self.assertEqual(code, 0)
            fc = _json_tail(out)
            self.assertEqual(fc["projected_month_total_usd"],
                             expected["forecast_2026-11"]["projected_month_total_usd"])
            self.assertFalse(fc["low_confidence"])

            code, out = _run(["budget", "--store", store, "--set", "2.50"])
            self.assertEqual(code, 0)
            code, out = _run(["budget", "--store", store, "--check",
                              "--period", "2026-11", "--today", "2026-11-24"])
            self.assertEqual(code, 0)
            result = _json_tail(out)
            self.assertEqual(result["status"], "AT_RISK")  # 2.10 / 2.50 = 84%
            self.assertEqual(result["remaining_usd"], 0.4)

    def test_import_jsonl_matches_csv(self):
        with tempfile.TemporaryDirectory() as d:
            s1, s2 = str(Path(d) / "a"), str(Path(d) / "b")
            _run(["import", "--store", s1, "--file", str(EXAMPLES / "usage.csv")])
            _run(["import", "--store", s2, "--file", str(EXAMPLES / "usage.jsonl")])
            _, out1 = _run(["report", "--store", s1, "--period", "2026-11"])
            _, out2 = _run(["report", "--store", s2, "--period", "2026-11"])
            self.assertEqual(_json_tail(out1), _json_tail(out2))

    def test_record_and_report(self):
        with tempfile.TemporaryDirectory() as d:
            store = str(Path(d) / "store")
            code, out = _run(["record", "--store", store, "--tool", "claude",
                              "--model", "sonnet", "--input", "100",
                              "--output", "50", "--cost", "0.03",
                              "--at", "2026-11-02"])
            self.assertEqual(code, 0)
            self.assertIn("recorded", out)
            code, out = _run(["report", "--store", store, "--period", "2026-11"])
            report = _json_tail(out)
            self.assertEqual(report["events"], 1)
            self.assertEqual(report["priced_cost_usd"], 0.03)

    def test_record_negative_fails(self):
        with tempfile.TemporaryDirectory() as d:
            code, _ = _run(["record", "--store", str(Path(d) / "s"),
                            "--tool", "x", "--model", "y",
                            "--input", "-1", "--output", "0",
                            "--at", "2026-11-02"])
            self.assertEqual(code, 2)

    def test_import_bad_rows_reported_not_silent(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.csv"
            bad.write_text(
                "date,tool,model,input_tokens,output_tokens,cost_usd\n"
                "2026-11-02,claude,m,100,50,0.03\n"
                "bad,claude,m,100,50,0.03\n")
            code, out = _run(["import", "--store", str(Path(d) / "s"),
                              "--file", str(bad)])
            self.assertEqual(code, 0)
            self.assertIn("imported 1 rows, skipped 1", out)
            self.assertIn("line 3", out)

    def test_init_writes_templates(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = _run(["init", "--dir", str(Path(d) / "t")])
            self.assertEqual(code, 0)
            self.assertTrue((Path(d) / "t" / "usage.csv").exists())
            self.assertTrue((Path(d) / "t" / "usage.jsonl").exists())

    def test_budget_check_without_budget(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = _run(["budget", "--store", str(Path(d) / "s"),
                              "--check", "--period", "2026-11"])
            self.assertEqual(code, 0)
            self.assertIn("no budget set", out)


if __name__ == "__main__":
    unittest.main()
