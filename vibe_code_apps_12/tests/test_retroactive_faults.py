"""Retroactive fault painting: (True, window_rows) and apply_faults()."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import readings_to_rows, sweep_rule  # noqa: E402


def _rows(n: int = 8) -> list[dict]:
    readings = [
        {"ts_ms": 1_000_000 + i * 60_000, "degF": 70.0 + (0.1 if i < 5 else 0.0)}
        for i in range(n)
    ]
    return readings_to_rows(readings)


class TestRetroactiveFaults(unittest.TestCase):
    def test_tuple_return_paints_window(self) -> None:
        code = """
def evaluate(row, cfg, prev_row=None, rows=None):
    if row["row"] == 5:
        return True, rows[2:7]
    return False
"""
        rows = _rows(8)
        flags, events = sweep_rule(code, {}, rows, capture_print=False)
        self.assertEqual(flags[2:7], [1, 1, 1, 1, 1])
        self.assertEqual(flags[0], 0)
        self.assertEqual(sum(flags), 5)
        summary = [e for e in events if e.get("type") == "summary"][0]
        self.assertEqual(summary["flagged"], 5)
        self.assertEqual(summary["sweep_mode"], "per_row")

    def test_apply_faults_batch(self) -> None:
        code = """
def evaluate(row, cfg, prev_row=None, rows=None):
    return row["row"] >= 3, rows[max(0, row["row"] - 2) : row["row"] + 1]

def apply_faults(rows, cfg):
    flags = [0] * len(rows)
    for row in rows:
        hit, window_rows = evaluate(row, cfg, rows=rows)
        if hit:
            for w in window_rows:
                flags[w["row"]] = 1
    return flags
"""
        rows = _rows(6)
        flags, events = sweep_rule(code, {}, rows, capture_print=False)
        self.assertGreater(sum(flags), 3)
        summary = [e for e in events if e.get("type") == "summary"][0]
        self.assertEqual(summary["sweep_mode"], "apply_faults")

    def test_bool_still_flags_current_row_only(self) -> None:
        code = """
def evaluate(row, cfg, prev_row=None, rows=None):
    return row["row"] == 2
"""
        rows = _rows(5)
        flags, _ = sweep_rule(code, {}, rows, capture_print=False)
        self.assertEqual(flags, [0, 0, 1, 0, 0])


if __name__ == "__main__":
    unittest.main()
