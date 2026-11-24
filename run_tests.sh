#!/bin/bash
# TokenTally v1: unit suite + demo e2e. Stdlib only, no network.
set -e
cd "$(dirname "$0")"

echo "=== unit tests ==="
python3 -m unittest discover -s tests -v

echo
echo "=== demo e2e: import examples, report, forecast, budget ==="
DEMO="$(mktemp -d)/store"
python3 -m tokentally import --store "$DEMO" --file examples/usage.csv
echo "--- report (2026-11) ---"
python3 -m tokentally report --store "$DEMO" --period 2026-11
echo "--- forecast (2026-11, today pinned to 2026-11-24) ---"
python3 -m tokentally forecast --store "$DEMO" --period 2026-11 --today 2026-11-24
echo "--- budget: set \$2.50, check ---"
python3 -m tokentally budget --store "$DEMO" --set 2.50
python3 -m tokentally budget --store "$DEMO" --check --period 2026-11 --today 2026-11-24
echo "--- check against hand-computed expected report ---"
python3 - <<PYEOF
import json, subprocess, sys
from pathlib import Path
out = subprocess.run([sys.executable, "-m", "tokentally", "report",
                      "--store", "$DEMO", "--period", "2026-11"],
                     capture_output=True, text=True, check=True).stdout
report = json.loads(out[out.index("{"):])
expected = json.loads(Path("examples/expected-report.json").read_text())
assert report["total_tokens"] == expected["total_tokens"], report
assert report["priced_cost_usd"] == expected["priced_cost_usd"], report
assert report["unpriced_events"] == expected["unpriced_events"], report
assert report["daily_average_cost_usd"] == expected["daily_average_cost_usd"], report
print("demo report matches hand-computed expected totals: "
      f"{report['total_tokens']} tokens, "
      f"\${report['priced_cost_usd']:.2f} priced, "
      f"{report['unpriced_events']} unpriced, "
      f"daily avg \${report['daily_average_cost_usd']:.2f}")
print("demo store:", "$DEMO")
print("demo done.")
PYEOF
