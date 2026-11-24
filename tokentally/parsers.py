"""Parsing and validation for usage rows.

Two import formats, both with the same fields:
  date, tool, model, input_tokens, output_tokens, cost_usd
  - date: YYYY-MM-DD
  - cost_usd: decimal string, may be empty (= unpriced)
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

FIELDS = ["date", "tool", "model", "input_tokens", "output_tokens", "cost_usd"]
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(value):
    """Parse a YYYY-MM-DD date, raising ValueError otherwise."""
    if not isinstance(value, str) or not _DATE_RE.match(value.strip()):
        raise ValueError(f"bad date: {value!r} (expected YYYY-MM-DD)")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"bad date: {value!r}") from exc


def parse_timestamp(value):
    """Parse an ISO-8601 timestamp or date; returns (date, datetime)."""
    if value is None:
        now = datetime.now()
        return now.date(), now
    text = str(value).strip()
    if _DATE_RE.match(text):
        d = date.fromisoformat(text)
        return d, datetime(d.year, d.month, d.day)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"bad timestamp: {value!r} (expected ISO-8601)") from exc
    return dt.date(), dt


def _int_field(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer, got {value!r}")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.strip() != "":
        try:
            result = int(value.strip())
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer, got {value!r}") from exc
        if str(result) != value.strip() and not re.match(r"^[+-]?\d+$", value.strip()):
            raise ValueError(f"{name} must be an integer, got {value!r}")
    else:
        raise ValueError(f"{name} is required and must be an integer")
    if result < 0:
        raise ValueError(f"{name} must be >= 0, got {result}")
    return result


def _cost_field(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        result = Decimal(str(value))
    elif isinstance(value, str) and value.strip() == "":
        return None
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError(f"cost_usd must be a number, got {value!r}") from exc
    else:
        raise ValueError(f"cost_usd must be a number, got {value!r}")
    if result < 0:
        raise ValueError(f"cost_usd must be >= 0, got {result}")
    if result.is_nan() or result.is_infinite():
        raise ValueError("cost_usd must be a finite number")
    return result


def _nonempty_str(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required and must be a non-empty string")
    return value.strip()


def normalize_row(data, at=None):
    """Validate a raw row dict and return a normalized row.

    data: mapping with date/tool/model/input_tokens/output_tokens/cost_usd.
    at: optional ISO-8601 timestamp overriding the date.
    """
    if at is not None:
        row_date, _ = parse_timestamp(at)
    else:
        row_date = parse_date(data.get("date"))
    return {
        "date": row_date.isoformat(),
        "tool": _nonempty_str(data.get("tool"), "tool"),
        "model": _nonempty_str(data.get("model"), "model"),
        "input_tokens": _int_field(data.get("input_tokens"), "input_tokens"),
        "output_tokens": _int_field(data.get("output_tokens"), "output_tokens"),
        "cost_usd": _cost_field(data.get("cost_usd")),
        "source": str(data.get("source") or "manual"),
    }


def parse_csv(path, tool_override=None):
    """Parse a usage CSV. Returns (rows, errors); errors are (line_no, msg)."""
    rows, errors = [], []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or [h.strip() for h in reader.fieldnames] != FIELDS:
            raise ValueError(
                f"CSV header must be exactly: {','.join(FIELDS)} "
                f"(got: {','.join(reader.fieldnames or [])})"
            )
        for line_no, raw in enumerate(reader, start=2):
            try:
                data = {k: (raw.get(k) or "") for k in FIELDS}
                if tool_override:
                    data["tool"] = tool_override
                rows.append(normalize_row(data))
            except ValueError as exc:
                errors.append((line_no, str(exc)))
    return rows, errors


def parse_jsonl(path, tool_override=None):
    """Parse a usage JSONL file. Returns (rows, errors); errors are (line_no, msg)."""
    rows, errors = [], []
    with open(path, encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append((line_no, f"invalid JSON: {exc.msg}"))
                continue
            if not isinstance(data, dict):
                errors.append((line_no, "line is not a JSON object"))
                continue
            try:
                if tool_override:
                    data = dict(data, tool=tool_override)
                rows.append(normalize_row(data))
            except ValueError as exc:
                errors.append((line_no, str(exc)))
    return rows, errors


def parse_import_file(path, tool_override=None):
    """Dispatch on suffix: .csv or .jsonl only; anything else is an error."""
    lower = str(path).lower()
    if lower.endswith(".csv"):
        return parse_csv(path, tool_override)
    if lower.endswith(".jsonl"):
        return parse_jsonl(path, tool_override)
    raise ValueError(f"unsupported import format: {path} (only .csv and .jsonl)")
