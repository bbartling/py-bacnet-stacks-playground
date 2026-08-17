"""Parse EnergyPlus eplusout.err / .end quality gates."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

_END_RE = re.compile(
    r"EnergyPlus Completed Successfully--\s*(\d+)\s*Warning;\s*(\d+)\s*Severe Errors",
    re.I,
)
_FATAL_RE = re.compile(r"\*\*\s*Fatal\s*\*\*", re.I)
_SEVERE_RE = re.compile(r"\*\*\s*Severe\s*\*\*", re.I)
_WARN_RE = re.compile(r"\*\*\s*Warning\s*\*\*", re.I)


def parse_eplus_err(err_path: Path, end_path: Path | None = None) -> dict[str, Any]:
    err_path = Path(err_path)
    text = err_path.read_text(encoding="utf-8", errors="replace") if err_path.is_file() else ""
    end_text = ""
    if end_path and Path(end_path).is_file():
        end_text = Path(end_path).read_text(encoding="utf-8", errors="replace")
    elif err_path.is_file():
        sibling = err_path.with_suffix(".end")
        if sibling.is_file():
            end_text = sibling.read_text(encoding="utf-8", errors="replace")

    severe_n = len(_SEVERE_RE.findall(text))
    fatal_n = len(_FATAL_RE.findall(text))
    warn_n = len(_WARN_RE.findall(text))
    completed = "EnergyPlus Completed Successfully" in (end_text or text)
    m = _END_RE.search(end_text or text)
    if m:
        warn_n = int(m.group(1))
        severe_n = int(m.group(2))

    first_severe = next((ln.strip() for ln in text.splitlines() if _SEVERE_RE.search(ln)), None)
    first_fatal = next((ln.strip() for ln in text.splitlines() if _FATAL_RE.search(ln)), None)
    kinds: Counter[str] = Counter()
    phase_air = {"warmup": 0, "sizing": 0, "scored_runtime": 0}
    coil_hits: list[dict[str, Any]] = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if "mass flow rate is smaller than 25%" in ln.lower():
            n = 1
            ctx = "\n".join(lines[i : i + 6])
            for nxt in lines[i + 1 : i + 6]:
                m = re.search(r"This error occurred\s+(\d+)\s+total times", nxt, re.I)
                if m:
                    n = int(m.group(1))
                    break
            kinds["w2a_low_airflow"] += n
            blob = ctx.lower()
            if "during warmup" in blob or "warmup" in ln.lower():
                phase = "warmup"
            elif "during sizing" in blob or "sizing period" in blob:
                phase = "sizing"
            else:
                phase = "scored_runtime"
            phase_air[phase] += n
            coil = None
            for nxt in lines[i : i + 8]:
                mcoil = re.search(r"Coil:Heating:WaterToAirHeatPump:EquationFit[=:]?\s*([^\s,;]+)", nxt)
                if mcoil:
                    coil = mcoil.group(1)
                    break
            coil_hits.append({"phase": phase, "n": n, "coil": coil, "line": ln.strip()[:240]})
        if "GetActuatorHandle" in ln or "Actuator Handle" in ln:
            kinds["actuator_handle"] += 1
        if "DATA PERIOD" in ln and "year" in ln.lower():
            kinds["data_period_year"] += 1

    ok = completed and fatal_n == 0 and severe_n == 0
    return {
        "ok": ok,
        "completed_successfully": completed,
        "warning_count": warn_n,
        "severe_count": severe_n,
        "fatal_count": fatal_n,
        "first_severe": first_severe,
        "first_fatal": first_fatal,
        "recurring": dict(kinds),
        "w2a_low_airflow_by_phase": phase_air,
        "w2a_low_airflow_events": coil_hits,
        "err_path": str(err_path) if err_path.is_file() else None,
    }


DEFAULT_MAX_W2A_LOW_AIRFLOW = None


def assert_eplus_quality(
    gate: dict[str, Any],
    *,
    allow_severe: tuple[str, ...] = (),
    max_w2a_low_airflow: int | None = DEFAULT_MAX_W2A_LOW_AIRFLOW,
) -> None:
    """Weather DATA PERIOD Severe is never allowlisted.

    ``max_w2a_low_airflow`` is None for historical A04 reproduction. Stage B
    candidates must pass a frozen bound (typically 0 printed coil warnings).
    """
    if gate.get("fatal_count", 0) != 0:
        raise ValueError(f"EnergyPlus Fatal: {gate.get('first_fatal')}")
    if not gate.get("completed_successfully"):
        raise ValueError("EnergyPlus did not complete successfully")
    severe = int(gate.get("severe_count") or 0)
    if severe != 0:
        first = str(gate.get("first_severe") or "")
        if "DATA PERIOD" in first:
            raise ValueError("EnergyPlus Severe DATA PERIOD year missing — stage a year-aware EPW")
        if not (allow_severe and any(a in first for a in allow_severe)):
            raise ValueError(f"EnergyPlus Severe not allowlisted: {first}")
    if max_w2a_low_airflow is not None:
        n_air = int((gate.get("recurring") or {}).get("w2a_low_airflow") or 0)
        if n_air > int(max_w2a_low_airflow):
            raise ValueError(
                f"EnergyPlus W2A low-airflow warnings={n_air} exceed max_w2a_low_airflow={max_w2a_low_airflow}"
            )
