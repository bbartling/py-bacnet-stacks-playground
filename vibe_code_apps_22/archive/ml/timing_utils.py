"""Wall-clock timing helpers for tutorial notebooks (train + inference)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


def format_hms(seconds: float) -> str:
    """Format elapsed seconds as ``Hh Mm Ss``.

    Examples: ``0h 00m 0.0s``, ``0h 01m 05s``, ``1h 01m 01s``.
    """
    if seconds is None:
        return "n/a"
    try:
        total = float(seconds)
    except (TypeError, ValueError):
        return "n/a"
    if total != total:  # NaN
        return "n/a"
    total = max(0.0, total)
    h = int(total // 3600)
    rem = total - 3600 * h
    m = int(rem // 60)
    s = rem - 60 * m
    if total < 10:
        return f"{h}h {m:02d}m {s:.1f}s"
    return f"{h}h {m:02d}m {int(round(s)):02d}s"


@dataclass
class Stopwatch:
    """Simple wall-clock stopwatch (context-manager friendly)."""

    name: str = ""
    _t0: float | None = None
    _elapsed: float | None = None

    def start(self) -> Stopwatch:
        self._t0 = time.perf_counter()
        self._elapsed = None
        return self

    def stop(self) -> float:
        if self._t0 is None:
            raise RuntimeError("Stopwatch was not started")
        self._elapsed = time.perf_counter() - self._t0
        return self._elapsed

    @property
    def elapsed(self) -> float:
        if self._elapsed is not None:
            return self._elapsed
        if self._t0 is None:
            return 0.0
        return time.perf_counter() - self._t0

    def __enter__(self) -> Stopwatch:
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.stop()


@dataclass
class TimingReport:
    """Accumulate named timings and print an H:M:S summary table."""

    entries: list[tuple[str, float]] = field(default_factory=list)

    def record(self, name: str, seconds: float) -> None:
        self.entries.append((name, float(seconds)))

    def time(self, name: str) -> _TimedSection:
        return _TimedSection(self, name)

    def total_seconds(self) -> float:
        return float(sum(s for _, s in self.entries))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [{"name": n, "seconds": s, "hms": format_hms(s)} for n, s in self.entries],
            "total_seconds": self.total_seconds(),
            "total_hms": format_hms(self.total_seconds()),
        }

    def write_json(self, path: Any, *, extra: dict[str, Any] | None = None) -> None:
        from pathlib import Path
        import json

        doc = self.to_dict()
        if extra:
            doc.update(extra)
        Path(path).write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def print_summary(self, title: str = "Timing summary") -> None:
        print(f"\n=== {title} ===", flush=True)
        if not self.entries:
            print("  (no timings recorded)", flush=True)
            return
        width = max(len(n) for n, _ in self.entries)
        for name, sec in self.entries:
            print(f"  {name:<{width}}  {format_hms(sec)}  ({sec:.3f} s)", flush=True)
        print(f"  {'TOTAL':<{width}}  {format_hms(self.total_seconds())}", flush=True)


@dataclass
class _TimedSection:
    report: TimingReport
    name: str
    _sw: Stopwatch = field(default_factory=Stopwatch)

    def __enter__(self) -> Stopwatch:
        return self._sw.start()

    def __exit__(self, *exc: Any) -> None:
        self._sw.stop()
        self.report.record(self.name, self._sw.elapsed)
