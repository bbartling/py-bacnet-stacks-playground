"""Host and campaign compute telemetry for residential DSM runs."""
from __future__ import annotations

import json
import os
import platform
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence


def collect_host_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "schema": "vibe23.host_info.v1",
        "hostname": platform.node(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "collected_at_unix": time.time(),
    }
    try:
        import psutil  # type: ignore

        info["ram_total_gb"] = round(psutil.virtual_memory().total / (1024**3), 2)
        info["psutil"] = True
    except Exception:
        info["psutil"] = False
    return info


def write_host_json(path: Path | str, info: dict[str, Any] | None = None) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = info or collect_host_info()
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


@dataclass
class PerRunTelemetry:
    candidate_id: str
    wall_seconds: float
    process_returncode: int
    fatal_count: int = 0
    severe_count: int = 0
    warning_count: int = 0
    peak_kw: float | None = None
    total_kwh: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        body = asdict(self)
        body["extra"] = dict(self.extra)
        return body


@dataclass
class CampaignCompute:
    runs: list[PerRunTelemetry]
    campaign_wall_seconds: float

    def summary(self) -> dict[str, Any]:
        walls = [float(run.wall_seconds) for run in self.runs]
        process_seconds = float(sum(walls))
        return {
            "schema": "vibe23.campaign_compute.v1",
            "run_count": len(self.runs),
            "campaign_wall_seconds": float(self.campaign_wall_seconds),
            "aggregate_process_seconds": process_seconds,
            "wall_p50": _percentile(walls, 50),
            "wall_p90": _percentile(walls, 90),
            "wall_p95": _percentile(walls, 95),
            "sims_per_minute": (
                (60.0 * len(walls) / self.campaign_wall_seconds) if self.campaign_wall_seconds > 0 else None
            ),
        }


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (q / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)
