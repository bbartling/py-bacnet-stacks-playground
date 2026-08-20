"""EnergyPlus process watchdog. Never leave a hung engine for hours."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class WatchdogTimeout(RuntimeError):
    """Startup, no-progress, or overall EnergyPlus deadline exceeded."""


@dataclass
class WatchdogLimits:
    startup_s: float = 300.0
    no_progress_s: float = 180.0
    overall_s: float = 3600.0


@dataclass
class EplusWatchdog:
    artifact_dir: Path
    limits: WatchdogLimits = field(default_factory=WatchdogLimits)
    pid: int | None = None

    def __post_init__(self) -> None:
        self.artifact_dir = Path(self.artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self._t0 = time.monotonic()
        self._last = self._t0
        self._started = False
        self.last_note = "constructed"
        self.last_callback_utc = datetime.now(timezone.utc).isoformat()

    def mark_started(self, *, pid: int | None = None, note: str = "started") -> None:
        self._started = True
        self.pid = int(pid) if pid is not None else os.getpid()
        self.heartbeat(note)

    def heartbeat(self, note: str = "progress") -> None:
        now = time.monotonic()
        if not self._started:
            if now - self._t0 > float(self.limits.startup_s):
                self.fail_artifact("startup_deadline")
                raise WatchdogTimeout(f"EnergyPlus startup exceeded {self.limits.startup_s}s")
        elif now - self._last > float(self.limits.no_progress_s):
            self.fail_artifact("no_progress_deadline")
            raise WatchdogTimeout(f"EnergyPlus no-progress exceeded {self.limits.no_progress_s}s")
        if now - self._t0 > float(self.limits.overall_s):
            self.fail_artifact("overall_deadline")
            raise WatchdogTimeout(f"EnergyPlus overall exceeded {self.limits.overall_s}s")
        self._last = now
        self.last_note = str(note)
        self.last_callback_utc = datetime.now(timezone.utc).isoformat()

    def snapshot(self) -> dict[str, Any]:
        return {
            "pid": self.pid or os.getpid(),
            "started": self._started,
            "elapsed_s": round(time.monotonic() - self._t0, 3),
            "last_note": self.last_note,
            "last_callback_utc": self.last_callback_utc,
            "limits": {
                "startup_s": self.limits.startup_s,
                "no_progress_s": self.limits.no_progress_s,
                "overall_s": self.limits.overall_s,
            },
        }

    def fail_artifact(self, reason: str) -> Path:
        path = self.artifact_dir / "failed.json"
        body = {
            "failed": True,
            "reason": str(reason),
            "watchdog": self.snapshot(),
        }
        path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        return path

    def run(self, fn: Callable[[], Any], *, note: str = "run") -> Any:
        self.heartbeat(f"before:{note}")
        try:
            out = fn()
        except WatchdogTimeout:
            raise
        except Exception as exc:  # noqa: BLE001
            self.fail_artifact(f"exception:{type(exc).__name__}:{exc}")
            raise
        self.heartbeat(f"after:{note}")
        return out
