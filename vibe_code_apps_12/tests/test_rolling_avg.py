"""Tests for browser-style 1-min avg (inline in rule code, no backend helper)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import aux_series_from_rows, readings_to_rows, sweep_rule  # noqa: E402

_ATTACH_CODE = '''
_buckets_done = False

def _attach_1min_avg(rows, bucket_ms=60000):
    buckets = {}
    for i, r in enumerate(rows):
        r["degF_raw"] = float(r["degF"])
        b = (int(r["ts_ms"]) // bucket_ms) * bucket_ms
        buckets.setdefault(b, []).append(i)
    for indices in buckets.values():
        avg_f = sum(rows[i]["degF_raw"] for i in indices) / len(indices)
        for i in indices:
            rows[i]["degF_1min_avg"] = avg_f

def evaluate(row, cfg, prev_row=None, rows=None):
    global _buckets_done
    if rows is not None and not _buckets_done:
        _attach_1min_avg(rows)
        _buckets_done = True
    return False
'''


class TestBrowserStyleRollingAvg(unittest.TestCase):
    def test_inline_attach_sets_avg_on_rows(self) -> None:
        rows = [
            {"row": 0, "ts_ms": 0, "ts": "t0", "degF": 70.0, "degC": 21.0},
            {"row": 1, "ts_ms": 10_000, "ts": "t1", "degF": 80.0, "degC": 26.0},
            {"row": 2, "ts_ms": 20_000, "ts": "t2", "degF": 90.0, "degC": 32.0},
        ]
        sweep_rule(_ATTACH_CODE, {}, rows, capture_print=False)
        self.assertEqual(rows[0]["degF_1min_avg"], 80.0)
        self.assertEqual(rows[2]["degF_1min_avg"], 80.0)
        self.assertEqual(rows[0]["degF_raw"], 70.0)

    def test_aux_series_reads_student_keys(self) -> None:
        readings = [
            {"ts_ms": i * 10_000, "degF": 70.0 if i < 5 else 90.0, "degC": 21.0}
            for i in range(10)
        ]
        rows = readings_to_rows(readings)
        sweep_rule(_ATTACH_CODE, {}, rows, capture_print=False)
        aux = aux_series_from_rows(rows)
        self.assertIn("degF_1min_avg", aux)
        self.assertEqual(len(aux["degF_1min_avg"]), len(readings))


if __name__ == "__main__":
    unittest.main()
