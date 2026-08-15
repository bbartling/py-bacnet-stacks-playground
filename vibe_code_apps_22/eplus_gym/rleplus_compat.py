"""Vendored generic rleplus helpers so CI works before the fork is published."""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Union

import numpy as np

ActionLike = Union[float, int, Sequence[float], np.ndarray]


def meter_lookup_key(name: str) -> str:
    return str(name).split("[", 1)[0].strip().upper()


def meter_indices_from_api_csv(raw: Union[bytes, str]) -> Dict[str, int]:
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    indices: Dict[str, int] = {}
    in_meters = False
    idx = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "**METERS**":
            in_meters = True
            continue
        if in_meters and stripped.startswith("**"):
            break
        if in_meters and stripped.upper().startswith("OUTPUTMETER,"):
            parts = stripped.split(",")
            if len(parts) >= 2:
                indices[meter_lookup_key(parts[1])] = idx
                idx += 1
    return indices


def missing_handle(handle: int) -> bool:
    return int(handle) == -1


def normalize_action(action: ActionLike, n_actuators: int) -> Union[float, List[float]]:
    n = int(n_actuators)
    if n < 1:
        raise ValueError("n_actuators must be >= 1")
    if n == 1:
        if isinstance(action, (list, tuple, np.ndarray)):
            return float(np.asarray(action, dtype=np.float64).reshape(-1)[0])
        return float(action)
    if isinstance(action, (float, int, np.floating, np.integer)):
        vals = [float(action)] * n
    else:
        vals = [float(x) for x in np.asarray(action, dtype=np.float64).reshape(-1)]
        if len(vals) == 1:
            vals = vals * n
    if len(vals) != n:
        raise ValueError(f"expected {n} actuator values, got {len(vals)}")
    if any(v != v or v in (float("inf"), float("-inf")) for v in vals):
        raise ValueError(f"non-finite action values: {vals}")
    return vals


def try_rleplus_helpers(*, allow_vendored_fallback: bool | None = None):
    """Prefer published rleplus helpers. Fail closed unless explicitly allowed."""
    import os

    if allow_vendored_fallback is None:
        allow_vendored_fallback = os.environ.get("VIBE22_ALLOW_VENDORED_FALLBACK", "").strip() in {
            "1",
            "true",
            "TRUE",
            "yes",
        }
    try:
        from eplus_gym.rleplus_path import ensure_rleplus, rleplus_git_sha

        root = ensure_rleplus()
        from rleplus.env.actions import normalize_action as na
        from rleplus.env.meters import meter_indices_from_api_csv as mic
        from rleplus.env.meters import meter_lookup_key as mlk
        from rleplus.env.meters import missing_handle as mh

        _ = (root, rleplus_git_sha)
        return na, mic, mlk, mh
    except Exception as exc:  # noqa: BLE001
        if not allow_vendored_fallback:
            raise RuntimeError(
                "rllib-energyplus generic helpers unavailable; set "
                "VIBE22_ALLOW_VENDORED_FALLBACK=1 to watermark a vendored run"
            ) from exc
        return normalize_action, meter_indices_from_api_csv, meter_lookup_key, missing_handle
