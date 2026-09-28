"""Minimal Zinc codec used by the fake Haystack server.

The implementation intentionally covers the scalar values used by the demo
(refs, strings, numbers, booleans, dates/datetimes, null and marker tags),
while preserving unknown values as strings.  It is not intended to replace a
full Project Haystack codec.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from dataclasses import dataclass
from typing import Any, Iterable
from zoneinfo import ZoneInfo


@dataclass
class Grid:
    meta: dict[str, Any]
    cols: list[str | "Column"]
    rows: list[dict[str, Any]]


class ZincError(ValueError):
    pass


@dataclass(frozen=True)
class Column:
    name: str
    meta: dict[str, Any] | None = None


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _encode_value(value: Any) -> str:
    if value is None:
        return "N"
    if value is True:
        return "T"
    if value is False:
        return "F"
    if isinstance(value, Ref):
        return "@" + value.value
    if isinstance(value, Marker):
        return "M"
    if isinstance(value, Quantity):
        return f"{value.value:g}{value.unit}"
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            text = value.isoformat(timespec="seconds")
        else:
            text = value.isoformat(timespec="seconds").replace("+00:00", "Z") + " " + _timezone_name(value.tzinfo)
        return text
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return _quote(value)
    return _quote(str(value))


def encode_grid(grid: Grid | dict[str, Any]) -> str:
    if isinstance(grid, dict):
        grid = Grid(grid.get("meta", {}), list(grid.get("cols", [])), list(grid.get("rows", [])))
    meta = ' '.join(f"{key}:{_encode_value(value)}" for key, value in grid.meta.items())
    lines = ['ver:"3.0"' + (" " + meta if meta else "")]
    lines.append(",".join(_encode_col(col) for col in grid.cols) if grid.cols else "empty")
    if grid.cols:
        for row in grid.rows:
            lines.append(",".join(_encode_value(row.get(_col_name(col))) for col in grid.cols))
    return "\n".join(lines) + "\n"


def _split_tokens(line: str) -> list[str]:
    """CSV-ish splitter honoring Zinc quoted strings and escapes."""
    out: list[str] = []
    token: list[str] = []
    quoted = False
    escaped = False
    for char in line:
        if escaped:
            token.append("\\")
            token.append(char)
            escaped = False
        elif quoted and char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
            token.append(char)
        elif char == "," and not quoted:
            out.append("".join(token).strip())
            token = []
        else:
            token.append(char)
    if quoted:
        raise ZincError("unterminated Zinc string")
    out.append("".join(token).strip())
    return out


def _decode_value(value: str) -> Any:
    if value in ("", "N", "null"):
        return None
    if value == "M":
        return Marker()
    if value == "T":
        return True
    if value == "F":
        return False
    if value.startswith("@"):
        return Ref(value[1:])
    if value.startswith('"') and value.endswith('"'):
        # _split_tokens removed the outer quotes, so this branch is retained
        # for callers that use _decode_value directly.
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?", value):
        return float(value)
    match = re.fullmatch(r"(-?(?:\d+\.\d*|\d*\.\d+|\d+))(.*)", value)
    if match and match.group(2) and re.fullmatch(r"[%°A-Za-zµ/_^*-]+", match.group(2)):
        return Quantity(float(match.group(1)), match.group(2))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            pass
    if "T" in value and re.match(r"\d{4}-\d{2}-\d{2}T", value):
        try:
            parts = value.replace("Z", "+00:00").split()
            parsed = dt.datetime.fromisoformat(parts[0])
            if len(parts) > 1 and parsed.tzinfo is None:
                zone_name = {"Chicago": "America/Chicago", "New_York": "America/New_York"}.get(parts[1], parts[1])
                parsed = parsed.replace(tzinfo=ZoneInfo(zone_name))
            elif len(parts) > 1:
                zone_name = {"Chicago": "America/Chicago", "New_York": "America/New_York"}.get(parts[1], parts[1])
                # Keep the instant from the encoded offset while retaining a
                # named zone for future formatting and DST-aware callers.
                parsed = parsed.astimezone(ZoneInfo(zone_name))
            return parsed
        except ValueError:
            pass
        except Exception:
            pass
    return value


@dataclass(frozen=True)
class Ref:
    value: str


@dataclass(frozen=True)
class Marker:
    pass


def decode_grid(text: str) -> Grid:
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n") if line.strip()]
    if not lines:
        return Grid({}, [], [])
    if not lines[0].startswith("ver:"):
        raise ZincError("Zinc grid must start with ver tag")
    meta: dict[str, Any] = {}
    for tag in _split_meta(lines[0]):
        if ":" not in tag:
            raise ZincError(f"invalid grid tag: {tag}")
        key, raw = tag.split(":", 1)
        meta[key] = _decode_quoted(raw) if raw.startswith('"') and raw.endswith('"') else _decode_value(raw)
    if len(lines) < 2 or lines[1] == "empty":
        return Grid(meta, [], [])
    cols = [_decode_col(token) for token in _split_tokens(lines[1])]
    rows: list[dict[str, Any]] = []
    for line in lines[2:]:
        values = _split_tokens(line)
        if len(values) != len(cols):
            raise ZincError(f"row has {len(values)} fields, expected {len(cols)}")
        rows.append(dict(zip((_col_name(col) for col in cols), (_decode_quoted_or_value(v) for v in values))))
    return Grid(meta, cols, rows)


def _decode_quoted(raw: str) -> str:
    if not (raw.startswith('"') and raw.endswith('"')):
        return raw
    inner = raw[1:-1]
    out: list[str] = []
    escaped = False
    for char in inner:
        if escaped:
            out.append({"n": "\n", "r": "\r", "t": "\t"}.get(char, char))
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            out.append(char)
    if escaped:
        out.append("\\")
    return "".join(out)


def _decode_quoted_or_value(value: str) -> Any:
    return _decode_quoted(value) if value.startswith('"') and value.endswith('"') else _decode_value(value)


def _split_meta(line: str) -> list[str]:
    out: list[str] = []
    token: list[str] = []
    quoted = False
    escaped = False
    for char in line:
        if escaped:
            token.append("\\")
            token.append(char)
            escaped = False
        elif quoted and char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
            token.append(char)
        elif char.isspace() and not quoted:
            if token:
                out.append("".join(token))
                token = []
        else:
            token.append(char)
    if token:
        out.append("".join(token))
    # Zinc DateTime literals carry an optional timezone name separated by a
    # space, so consume that suffix as part of the preceding key/value tag.
    merged: list[str] = []
    index = 0
    while index < len(out):
        current = out[index]
        if ":" in current and "T" in current.split(":", 1)[1] and index + 1 < len(out) and ":" not in out[index + 1]:
            current = current + " " + out[index + 1]
            index += 1
        merged.append(current)
        index += 1
    return merged


def _col_name(col: str | Column) -> str:
    return col.name if isinstance(col, Column) else col


def _encode_col(col: str | Column) -> str:
    if isinstance(col, Column) and col.meta:
        return col.name + " " + " ".join(f"{key}:{_encode_value(value)}" for key, value in col.meta.items())
    return _col_name(col)


def _decode_col(token: str) -> Column:
    bits = _split_meta(token)
    if not bits:
        raise ZincError("empty column name")
    meta: dict[str, Any] = {}
    for item in bits[1:]:
        if ":" not in item:
            continue
        key, raw = item.split(":", 1)
        meta[key] = _decode_quoted(raw) if raw.startswith('"') and raw.endswith('"') else _decode_value(raw)
    return Column(bits[0], meta)


def _timezone_name(tzinfo: dt.tzinfo) -> str:
    key = getattr(tzinfo, "key", None)
    if key == "America/Chicago":
        return "Chicago"
    if key == "America/New_York":
        return "New_York"
    if key:
        return key.replace("/", "_")
    return "UTC"


def row_grid(rows: Iterable[dict[str, Any]], meta: dict[str, Any] | None = None) -> Grid:
    rows = list(rows)
    cols: list[str] = []
    for row in rows:
        for key in row:
            if key not in cols:
                cols.append(key)
    return Grid(meta or {}, cols, rows)
