"""Parse EnergyPlus eplusout.err for warning / severe / fatal counts."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ErrSummary:
    path: str
    warnings: int
    severes: int
    fatals: int
    completed_successfully: bool
    summary_line: str
    severe_messages: tuple[str, ...]


_SEV = re.compile(r"\*\*\s*Severe\s*\*\*", re.I)
_WARN = re.compile(r"\*\*\s*Warning\s*\*\*", re.I)
_FATAL = re.compile(r"\*\*\s*Fatal\s*\*\*", re.I)
_DONE = re.compile(r"EnergyPlus Completed Successfully--\s*(\d+)\s*Warning;\s*(\d+)\s*Severe", re.I)
_TERM = re.compile(r"EnergyPlus Terminated--Fatal", re.I)


def parse_eplusout_err(path: Path | str) -> ErrSummary:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"missing eplusout.err: {p}")
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    severe_msgs: list[str] = []
    for i, line in enumerate(lines):
        if _SEV.search(line):
            # include following context line if present
            chunk = line.strip()
            if i + 1 < len(lines) and not lines[i + 1].strip().startswith("**"):
                chunk = chunk + " | " + lines[i + 1].strip()[:200]
            severe_msgs.append(chunk[:400])
    warnings = len(_WARN.findall(text))
    severes = len(_SEV.findall(text))
    fatals = len(_FATAL.findall(text))
    summary_line = ""
    completed = False
    for line in reversed(lines):
        m = _DONE.search(line)
        if m:
            summary_line = line.strip()
            completed = True
            # prefer summary totals when present
            warnings = int(m.group(1))
            severes = int(m.group(2))
            break
        if _TERM.search(line):
            summary_line = line.strip()
            completed = False
            break
    return ErrSummary(
        path=str(p),
        warnings=warnings,
        severes=severes,
        fatals=fatals,
        completed_successfully=completed and fatals == 0,
        summary_line=summary_line,
        severe_messages=tuple(severe_msgs[:40]),
    )
