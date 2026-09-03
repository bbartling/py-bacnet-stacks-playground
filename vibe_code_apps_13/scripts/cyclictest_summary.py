#!/usr/bin/env python3
"""Aggregate cyclictest per-thread T: lines into overall min/avg/max.

overall_min = minimum of all worker Min values
overall_max = maximum of all worker Max values
overall_avg = sample-weighted mean: sum(Avg_i * samples_i) / sum(samples_i)
  where samples_i is the parenthesized count on each T: line.

Host-risk indicator (NOT Clause 9 wire timing):
  60 bit times @ 38400 baud = 60 / 38400 s = 1.5625 ms = 1562.5 µs.
  This is an informational scheduling-risk comparison only.
  It is NOT a universal response deadline and NOT T_frame_abort conformance.

cyclictest -m means mlockall (lock memory), NOT one worker per CPU.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

THREAD_RE = re.compile(
    r"^T:\s*(\d+)\s*\(\s*(\d+)\s*\)\s*P:(\d+)\s*I:(\d+)\s*C:\s*(\d+)\s*"
    r"Min:\s*(\d+)\s*Act:\s*(\d+)\s*Avg:\s*(\d+)\s*Max:\s*(\d+)"
)

# Informational host scheduling-risk indicator only (60 bit @ 38400).
HOST_RISK_THRESHOLD_US = 1562.5

ThresholdAssessment = Literal["under", "exceeded", "unknown"]


@dataclass
class ThreadSummary:
    thread: int
    samples: int
    priority: int
    interval_us: int
    cycles: int
    min_us: int
    act_us: int
    avg_us: int
    max_us: int


@dataclass
class CyclictestSummary:
    thread_count: int
    overall_min_us: int
    overall_avg_us: float
    overall_max_us: int
    sched_policy: str
    sched_priority: int | None
    threads: list[ThreadSummary]

    def rounded_avg_us(self) -> int:
        return int(round(self.overall_avg_us))

    def scheduling_threshold_assessment(
        self, threshold_us: float = HOST_RISK_THRESHOLD_US
    ) -> ThresholdAssessment:
        if self.overall_max_us > threshold_us:
            return "exceeded"
        return "under"


def parse_cyclictest_text(text: str) -> CyclictestSummary | None:
    threads: list[ThreadSummary] = []
    for line in text.splitlines():
        m = THREAD_RE.match(line.strip())
        if not m:
            continue
        thread, samples, priority, interval, cycles, min_us, act, avg, max_us = m.groups()
        threads.append(
            ThreadSummary(
                thread=int(thread),
                samples=int(samples),
                priority=int(priority),
                interval_us=int(interval),
                cycles=int(cycles),
                min_us=int(min_us),
                act_us=int(act),
                avg_us=int(avg),
                max_us=int(max_us),
            )
        )
    if not threads:
        return None

    total_samples = sum(t.samples for t in threads)
    if total_samples > 0:
        weighted_avg = sum(t.avg_us * t.samples for t in threads) / total_samples
    else:
        weighted_avg = sum(t.avg_us for t in threads) / len(threads)

    priority = threads[0].priority
    return CyclictestSummary(
        thread_count=len(threads),
        overall_min_us=min(t.min_us for t in threads),
        overall_avg_us=weighted_avg,
        overall_max_us=max(t.max_us for t in threads),
        sched_policy="SCHED_FIFO",
        sched_priority=priority,
        threads=threads,
    )


def summary_to_dict(summary: CyclictestSummary) -> dict[str, Any]:
    data = asdict(summary)
    data["overall_avg_us_rounded"] = summary.rounded_avg_us()
    data["host_risk_threshold_us"] = HOST_RISK_THRESHOLD_US
    data["scheduling_threshold_assessment"] = summary.scheduling_threshold_assessment()
    data["wire_timing_measured"] = False
    data["clause9_conformance"] = "not_claimed"
    data["notes"] = (
        "cyclictest measures host scheduler latency, not Clause 9 wire turnaround; "
        "60-bit interval is an informational host-risk indicator only; "
        "cyclictest -m means mlockall, not one worker per CPU"
    )
    return data


def format_result_section(name: str, summary: CyclictestSummary) -> list[str]:
    avg_display = summary.rounded_avg_us()
    assessment = summary.scheduling_threshold_assessment()
    return [
        f"## {name}",
        f"- threads: {summary.thread_count}",
        f"- min: {summary.overall_min_us} us",
        f"- avg: {avg_display} us (sample-weighted across threads)",
        f"- max: {summary.overall_max_us} us",
        f"- sched: {summary.sched_policy} priority {summary.sched_priority}",
        f"- scheduling_threshold_assessment vs {HOST_RISK_THRESHOLD_US} us: **{assessment}**",
        f"- host-risk indicator only (60 bit @ 38400) — not Clause 9 / not wire turnaround",
        f"- wire_timing_measured: false; clause9_conformance: not_claimed",
        "",
    ]


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: cyclictest_summary.py <cyclictest-output.txt>", file=sys.stderr)
        return 2
    path = Path(args[0])
    summary = parse_cyclictest_text(path.read_text(errors="replace"))
    if summary is None:
        print("no T: worker lines found", file=sys.stderr)
        return 1
    print(json.dumps(summary_to_dict(summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
