"""Local JSON store: usage rows (JSONL) + monthly budget (JSON)."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .parsers import normalize_row, parse_timestamp


def _dec_to_str(value):
    if value is None:
        return None
    return str(value)


def _row_to_json(row):
    out = dict(row)
    out["cost_usd"] = _dec_to_str(row.get("cost_usd"))
    return out


def _row_from_json(data):
    row = dict(data)
    raw = row.get("cost_usd")
    if raw is None or raw == "":
        row["cost_usd"] = None
    else:
        try:
            row["cost_usd"] = Decimal(str(raw))
        except InvalidOperation as exc:
            raise ValueError(f"bad stored cost_usd: {raw!r}") from exc
    return row


class Store:
    """A directory holding usage.jsonl and budget.json."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.events_path = self.path / "usage.jsonl"
        self.budget_path = self.path / "budget.json"
        if not self.events_path.exists():
            self.events_path.touch()

    def load_rows(self):
        rows = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(_row_from_json(json.loads(line)))
        return rows

    def append_row(self, row):
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_row_to_json(row), sort_keys=True) + "\n")
        return row

    def record(self, tool, model, input_tokens, output_tokens, cost_usd=None,
               at=None, source="manual"):
        """Validate and append one usage row. Returns the row dict."""
        if at is None:
            from datetime import date as _date
            at = _date.today().isoformat()
        row = normalize_row({
            "date": None,
            "tool": tool,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "source": source,
        }, at=at)
        row["id"] = str(uuid.uuid4())
        return self.append_row(row)

    def add_rows(self, rows):
        for row in rows:
            self.append_row(row)
        return len(rows)

    def get_budget(self):
        if not self.budget_path.exists():
            return None
        data = json.loads(self.budget_path.read_text(encoding="utf-8"))
        return Decimal(str(data["monthly_budget_usd"]))

    def set_budget(self, amount):
        amount = Decimal(str(amount))
        if amount < 0:
            raise ValueError("budget must be >= 0")
        self.budget_path.write_text(
            json.dumps({"monthly_budget_usd": str(amount)}, indent=2) + "\n",
            encoding="utf-8",
        )
        return amount
