"""Stage a year-aware EPW copy. Never overwrite the source weather file."""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any

_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_data_periods(line: str) -> dict[str, str]:
    parts = [p.strip() for p in line.split(",")]
    return {
        "raw": line.strip(),
        "start": parts[5] if len(parts) > 5 else "",
        "end": parts[6] if len(parts) > 6 else "",
    }


def _token_has_year(token: str) -> bool:
    bits = [b for b in token.replace("-", "/").split("/") if b]
    return len(bits) >= 3


def epw_data_row_span(text: str) -> tuple[date, date] | None:
    first: date | None = None
    last: date | None = None
    for line in text.splitlines():
        if not line or line[0].isalpha() or line.startswith("!"):
            continue
        parts = line.split(",")
        if len(parts) < 4:
            continue
        try:
            y, mo, dy = int(parts[0]), int(parts[1]), int(parts[2])
            d = date(y, mo, dy)
        except ValueError:
            continue
        first = first or d
        last = d
    if first is None or last is None:
        return None
    return first, last


def year_qualify_data_periods(text: str) -> tuple[str, dict[str, Any]]:
    """Rewrite DATA PERIODS start/end to mm/dd/yyyy from AMY data rows."""
    span = epw_data_row_span(text)
    if span is None:
        raise ValueError("EPW has no data rows to year-qualify DATA PERIODS")
    start, end = span
    start_s = f"{start.month}/{start.day}/{start.year}"
    end_s = f"{end.month}/{end.day}/{end.year}"
    dow = _DAYS[start.weekday()]
    new_line = f"DATA PERIODS,1,1,Data,{dow},{start_s},{end_s}"
    out: list[str] = []
    old_raw = ""
    found = False
    for line in text.splitlines():
        if line.upper().startswith("DATA PERIODS"):
            old_raw = line.strip()
            out.append(new_line)
            found = True
        else:
            out.append(line)
    if not found:
        raise ValueError("EPW missing DATA PERIODS header")
    meta = {
        "source_data_periods": old_raw,
        "staged_data_periods": new_line,
        "span_start": start.isoformat(),
        "span_end": end.isoformat(),
        "source_had_year": _token_has_year(parse_data_periods(old_raw)["start"]),
    }
    return "\n".join(out) + "\n", meta


def stage_year_aware_epw(src: Path, dest: Path) -> dict[str, Any]:
    src = Path(src).resolve()
    dest = Path(dest)
    if dest.resolve() == src:
        raise ValueError("refusing to overwrite source EPW")
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8", errors="replace")
    staged_text, meta = year_qualify_data_periods(text)
    dest.write_text(staged_text, encoding="utf-8", newline="\n")
    rec = {
        "source_epw": str(src),
        "staged_epw": str(dest),
        "source_sha256": sha256_file(src),
        "staged_sha256": sha256_file(dest),
        **meta,
    }
    (dest.parent / "epw_stage.json").write_text(
        __import__("json").dumps(rec, indent=2) + "\n", encoding="utf-8"
    )
    return rec
