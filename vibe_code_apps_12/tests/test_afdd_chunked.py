"""Chunked AFDD evaluation (bounded memory, Arrow-only)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
_TESTS = Path(__file__).resolve().parent
for p in (_WEB, _TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from playground_core import chunked_evaluate_custom_rules, count_flags_in_ts_range, readings_to_rows  # noqa: E402

ARROW_HOT = """import pyarrow as pa
import pyarrow.compute as pc


def apply_faults_arrow(table, cfg, context=None):
    return pc.greater(pc.cast(table["degF"], pa.float64()), cfg["hot_f"])
"""


class TestAfddChunked(unittest.TestCase):
    def test_count_flags_in_ts_range(self) -> None:
        rows = readings_to_rows(
            [
                {"ts_ms": 0, "degF": 70.0, "degC": 21.0},
                {"ts_ms": 5000, "degF": 90.0, "degC": 32.0},
                {"ts_ms": 10000, "degF": 70.0, "degC": 21.0},
            ]
        )
        flags = {"r1": [0, 1, 1]}
        self.assertEqual(count_flags_in_ts_range(flags, rows, 0, 5000), {"r1": 0})
        self.assertEqual(count_flags_in_ts_range(flags, rows, 5000, 20000), {"r1": 2})

    def test_chunked_eval_merges_two_chunks(self) -> None:
        import time

        now_ms = int(time.time() * 1000)
        base = now_ms - 8 * 3600_000

        def fetch_interval(start_ms: int, end_ms_exclusive: int) -> list[dict]:
            out = []
            t = base
            while t < end_ms_exclusive:
                if t >= start_ms:
                    out.append(
                        {
                            "ts_ms": t,
                            "degF": 90.0 if t >= base + 3 * 3600_000 else 70.0,
                            "degC": 21.0,
                        }
                    )
                t += 600_000
            return out

        rules = [
            {
                "id": "hot",
                "enabled": True,
                "config": {"hot_f": 80},
                "code": ARROW_HOT,
            }
        ]
        summary = chunked_evaluate_custom_rules(
            rules=rules,
            lookback_hours=8,
            fetch_interval=fetch_interval,
            chunk_hours=4,
        )
        self.assertEqual(summary["afdd_format"], "chunked_arrow_v1")
        self.assertEqual(summary["fdd_backend"], "arrow")
        self.assertGreater(summary["chunk_count"], 1)
        self.assertGreater(summary["flag_counts"].get("hot", 0), 0)


if __name__ == "__main__":
    unittest.main()
