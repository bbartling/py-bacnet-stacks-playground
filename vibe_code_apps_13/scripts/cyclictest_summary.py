#!/usr/bin/env python3
"""Aggregate cyclictest per-thread T: lines into overall min/avg/max.

overall_min = minimum of all worker Min values
overall_max = maximum of all worker Max values
overall_avg = sample-weighted mean: sum(Avg_i * samples_i) / sum(samples_i)
  where samples_i is the parenthesized count on each T: line.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

THREAD_RE = re.compile(
    r"^T:\s*(\d+)\s*\(\s*(\d+)\s*\)\s*P:(\d+)\s*I:(\d+)\s*C:\s*(\d+)\s*"
    r"Min:\s*(\d+)\s*Act:\s*(\d+)\s*Avg:\s*(\d+)\s*Max:\s*(\d+)"
)


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
    return data


def write_summary_json(path: Path, summary: CyclictestSummary) -> None:
    path.write_text(json.dumps(summary_to_dict(summary), indent=2) + "\n")


def format_result_section(name: str, summary: CyclictestSummary) -> list[str]:
    avg_display = summary.rounded_avg_us()
    return [
        f"## {name}",
        f"- threads: {summary.thread_count}",
        f"- min: {summary.overall_min_us} us",
        f"- avg: {avg_display} us (sample-weighted across threads)",
        f"- max: {summary.overall_max_us} us",
        f"- sched: {summary.sched_policy} priority {summary.sched_priority}",
        f"- vs 1562 us (60 bit @ 38400): scheduling-risk indicator only — not Clause 9 conformance",
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
