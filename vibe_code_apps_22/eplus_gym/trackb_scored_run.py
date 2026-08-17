"""Track B scored-runperiod contract. Return code 0 is not sufficient."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from eplus_gym.objective import BAS_ZONE_COLS

ENGINE_EXECUTED_NO_VALID_SCORED_RUNPERIOD = "ENGINE_EXECUTED_NO_VALID_SCORED_RUNPERIOD"


def validate_scored_trackb_run(
    *,
    gate: Mapping[str, Any],
    returncode: int,
    rows: Sequence[Mapping[str, Any]],
    expected_day: str,
) -> dict[str, Any]:
    issues: list[str] = []
    severe = int(gate.get("severe_count") or 0)
    fatal = int(gate.get("fatal_count") or 0)
    if fatal:
        issues.append(f"fatal_count={fatal}")
    if severe:
        issues.append(f"severe_count={severe}")
    if not rows:
        issues.append("no scored trajectory rows")
    n = len(rows)
    if n and n != 96:
        issues.append(f"n_intervals={n} expected 96")
    days = {str(r.get("day") or "")[:10] for r in rows}
    if rows and days != {str(expected_day)[:10]}:
        issues.append(f"calendar {days} != {expected_day}")
    fac: list[float] = []
    for i, row in enumerate(rows):
        try:
            kw = float(row["facility_kw"])
        except (KeyError, TypeError, ValueError):
            issues.append(f"facility_kw missing at {i}")
            continue
        if kw != kw or kw in (float("inf"), float("-inf")):
            issues.append(f"non-finite facility_kw at {i}")
        fac.append(kw)
        for col in BAS_ZONE_COLS:
            if col in row:
                val = row[col]
            else:
                # allow ACTION_KEYS mapping in compact payloads
                val = None
                for key, alt in ((col, col),):
                    if key in row:
                        val = row[key]
                if val is None:
                    issues.append(f"missing zone {col} at {i}")
                    continue
            try:
                t = float(val)
            except (TypeError, ValueError):
                issues.append(f"non-finite zone {col} at {i}")
                continue
            if t != t:
                issues.append(f"NaN zone {col} at {i}")
    first_ts = str(rows[0].get("timestamp") or rows[0].get("day") or "") if rows else ""
    last_ts = str(rows[-1].get("timestamp") or rows[-1].get("day") or "") if rows else ""
    proven = not issues and n == 96 and severe == 0 and fatal == 0
    status = "VALID_SCORED_RUNPERIOD" if proven else ENGINE_EXECUTED_NO_VALID_SCORED_RUNPERIOD
    return {
        "ok": proven,
        "status": status,
        "scored_runtime_proven": proven,
        "n_intervals": n,
        "first_runtime_timestamp": first_ts,
        "last_runtime_timestamp": last_ts,
        "returncode": int(returncode),
        "issues": issues[:20],
        "engine_returncode_is_not_sufficient": True,
    }
