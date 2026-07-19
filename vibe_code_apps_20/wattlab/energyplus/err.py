"""Parse eplusout.err for Warning / Severe / Fatal diagnostics.

EnergyPlus err lines look like::

    ** Warning ** Weather file location will be used ...
    **   ~~~   ** ..Location object=CHICAGO_IL_USA TMY2-94846
    ** Severe  ** Node connection errors not checked ...
    **  Fatal  ** Errors occurred on processing input file.
    ************* EnergyPlus Completed Successfully-- 2 Warning; 0 Severe Errors.

Continuation lines (``**   ~~~   **``) are folded into the preceding message.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_MESSAGE_RE = re.compile(
    r"^\s*\*\*\s*(Warning|Severe|Fatal)\s*\*\*\s*(.*)$", re.IGNORECASE
)
_CONTINUATION_RE = re.compile(r"^\s*\*\*\s*~~~\s*\*\*\s*(.*)$")
_COMPLETED_RE = re.compile(r"EnergyPlus Completed Successfully", re.IGNORECASE)
_TERMINATED_RE = re.compile(r"EnergyPlus Terminated", re.IGNORECASE)


def parse_err_text(text: str) -> dict[str, Any]:
    """Parse err-file text into counts + severe/fatal message lists."""
    warnings = 0
    severe_messages: list[str] = []
    fatal_messages: list[str] = []
    current: list[str] | None = None
    completed = False
    terminated = False

    for raw in text.splitlines():
        m = _MESSAGE_RE.match(raw)
        if m:
            level = m.group(1).lower()
            message = m.group(2).strip()
            if level == "warning":
                warnings += 1
                current = None
            elif level == "severe":
                severe_messages.append(message)
                current = severe_messages
            else:
                fatal_messages.append(message)
                current = fatal_messages
            continue
        c = _CONTINUATION_RE.match(raw)
        if c and current:
            current[-1] = f"{current[-1]} {c.group(1).strip()}".strip()
            continue
        current = None
        if _COMPLETED_RE.search(raw):
            completed = True
        elif _TERMINATED_RE.search(raw):
            terminated = True

    severe = len(severe_messages)
    fatal = len(fatal_messages)
    return {
        "warnings": warnings,
        "severe": severe,
        "fatal": fatal,
        "severe_messages": severe_messages,
        "fatal_messages": fatal_messages,
        "completed_successfully": completed and not terminated,
        "terminated": terminated,
        # Severe diagnostics taint results even when the run completes.
        "results_suspect": severe > 0 or fatal > 0 or terminated,
        "ok": completed and not terminated and fatal == 0,
    }


def parse_err_file(path: Path) -> dict[str, Any]:
    """Parse an eplusout.err file; missing file returns a not-ok summary."""
    path = Path(path)
    if not path.is_file():
        return {
            "warnings": 0,
            "severe": 0,
            "fatal": 0,
            "severe_messages": [],
            "fatal_messages": [],
            "completed_successfully": False,
            "terminated": False,
            "results_suspect": True,
            "ok": False,
            "missing": True,
            "path": str(path),
        }
    out = parse_err_text(path.read_text(encoding="utf-8", errors="replace"))
    out["missing"] = False
    out["path"] = str(path)
    return out
