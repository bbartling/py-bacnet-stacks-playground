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
# Real EnergyPlus recurring block (line-broken):
#   This error occurred 46152 total times;
#   during Warmup 39052 times;
#   during Sizing 0 times.
_PHASE_BLOCK_RE = re.compile(
    r"This error occurred\s+(\d+)\s+total times;\s*"
    r".*?during\s+Warmup\s+(\d+)\s+times;\s*"
    r".*?during\s+Sizing\s+(\d+)\s+times",
    re.I | re.S,
)
_TOTAL_ONLY_RE = re.compile(r"This error occurred\s+(\d+)\s+total times", re.I)


def _parse_w2a_phase_block(blob: str) -> dict[str, Any]:
    m = _PHASE_BLOCK_RE.search(blob)
    if m:
        total = int(m.group(1))
        warmup = int(m.group(2))
        sizing = int(m.group(3))
        if total < warmup + sizing:
            return {
                "ok": False,
                "reason": "total_lt_warmup_plus_sizing",
                "total": total,
                "warmup": warmup,
                "sizing": sizing,
                "scored_runtime": None,
            }
        return {
            "ok": True,
            "reason": None,
            "total": total,
            "warmup": warmup,
            "sizing": sizing,
            "scored_runtime": total - warmup - sizing,
        }
    return {
        "ok": False,
        "reason": "phases_unparseable",
        "total": None,
        "warmup": None,
        "sizing": None,
        "scored_runtime": None,
    }


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
    phase_unparseable = False
    phase_fail_closed = False
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if "GetActuatorHandle" in ln or "Actuator Handle" in ln:
            kinds["actuator_handle"] += 1
        if "DATA PERIOD" in ln and "year" in ln.lower():
            kinds["data_period_year"] += 1
        if "mass flow rate is smaller than 25%" not in ln.lower():
            i += 1
            continue
        blob = "\n".join(lines[i : i + 12])
        parsed = _parse_w2a_phase_block(blob)
        total_m = _TOTAL_ONLY_RE.search(blob)
        n_print = int(total_m.group(1)) if total_m else 1
        kinds["w2a_low_airflow"] += n_print
        coil = None
        for nxt in lines[i : i + 12]:
            mcoil = re.search(r"Coil:Heating:WaterToAirHeatPump:EquationFit[=:]?\s*([^\s,;]+)", nxt)
            if mcoil:
                coil = mcoil.group(1)
                break
        if not parsed["ok"]:
            phase_unparseable = True
            phase_fail_closed = True
            coil_hits.append(
                {
                    "phase": "unparseable",
                    "n": n_print,
                    "coil": coil,
                    "line": ln.strip()[:240],
                    "reason": parsed["reason"],
                }
            )
            i += 1
            continue
        warmup = int(parsed["warmup"])
        sizing = int(parsed["sizing"])
        runtime = int(parsed["scored_runtime"])
        phase_air["warmup"] += warmup
        phase_air["sizing"] += sizing
        phase_air["scored_runtime"] += runtime
        coil_hits.append(
            {
                "phase": "scored_runtime" if runtime else ("warmup" if warmup else "sizing"),
                "n": n_print,
                "warmup": warmup,
                "sizing": sizing,
                "scored_runtime": runtime,
                "coil": coil,
                "line": ln.strip()[:240],
            }
        )
        i += 1

    ok = completed and fatal_n == 0 and severe_n == 0 and not phase_fail_closed
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
        "w2a_phase_unparseable": phase_unparseable,
        "w2a_phase_fail_closed": phase_fail_closed,
        "err_path": str(err_path) if err_path.is_file() else None,
    }


DEFAULT_MAX_W2A_LOW_AIRFLOW = None


def scored_runtime_w2a_count(gate: dict[str, Any]) -> int | None:
    if gate.get("w2a_phase_fail_closed") or gate.get("w2a_phase_unparseable"):
        return None
    phase = gate.get("w2a_low_airflow_by_phase") or {}
    if phase.get("scored_runtime") is None:
        return None
    return int(phase.get("scored_runtime") or 0)


def assert_eplus_quality(
    gate: dict[str, Any],
    *,
    allow_severe: tuple[str, ...] = (),
    max_w2a_low_airflow: int | None = DEFAULT_MAX_W2A_LOW_AIRFLOW,
    max_scored_runtime_w2a: int | None = None,
) -> None:
    """Weather DATA PERIOD Severe is never allowlisted.

    Gate Track B / quality on scored-runtime W2A only. Unparseable phases fail closed.
    ``max_w2a_low_airflow`` remains the historical printed-total bound (A04 reproduction).
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
    if gate.get("w2a_phase_fail_closed") and max_scored_runtime_w2a is not None:
        raise ValueError("EnergyPlus W2A phase block unparseable — fail closed")
    if max_scored_runtime_w2a is not None:
        n_rt = scored_runtime_w2a_count(gate)
        if n_rt is None:
            raise ValueError("EnergyPlus W2A scored-runtime unparseable — fail closed")
        if n_rt > int(max_scored_runtime_w2a):
            raise ValueError(
                f"EnergyPlus W2A scored-runtime warnings={n_rt} exceed max={max_scored_runtime_w2a}"
            )
    if max_w2a_low_airflow is not None:
        n_air = int((gate.get("recurring") or {}).get("w2a_low_airflow") or 0)
        if n_air > int(max_w2a_low_airflow):
            raise ValueError(
                f"EnergyPlus W2A low-airflow warnings={n_air} exceed max_w2a_low_airflow={max_w2a_low_airflow}"
            )
