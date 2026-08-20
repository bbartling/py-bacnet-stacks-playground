"""EnergyPlus watchdog unit tests. No live engine."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from eplus_gym.rl.eplus_watchdog import EplusWatchdog, WatchdogLimits, WatchdogTimeout


def test_startup_deadline_writes_failed_json(tmp_path: Path):
    dog = EplusWatchdog(tmp_path, WatchdogLimits(startup_s=0.01, no_progress_s=10, overall_s=10))
    time.sleep(0.03)
    with pytest.raises(WatchdogTimeout, match="startup"):
        dog.heartbeat()
    failed = tmp_path / "failed.json"
    assert failed.is_file()
    body = failed.read_text(encoding="utf-8")
    assert "startup_deadline" in body


def test_progress_heartbeat_ok(tmp_path: Path):
    dog = EplusWatchdog(tmp_path, WatchdogLimits(startup_s=5, no_progress_s=5, overall_s=5))
    dog.mark_started(pid=1, note="go")
    dog.heartbeat("tick")
    snap = dog.snapshot()
    assert snap["started"] is True
    assert snap["pid"] == 1
