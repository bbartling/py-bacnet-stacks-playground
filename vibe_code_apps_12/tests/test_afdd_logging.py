"""AfddLog and chunked error handling."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from afdd_logging import AfddLog, debug_payload  # noqa: E402
from playground_core import chunked_evaluate_custom_rules  # noqa: E402


class TestAfddLogging(unittest.TestCase):
    def test_log_snapshot(self) -> None:
        log = AfddLog(prefix="test")
        log.info("hello")
        log.warn("careful")
        snap = log.snapshot()
        self.assertEqual(snap[0], "hello")
        self.assertIn("WARN", snap[1])

    def test_debug_payload(self) -> None:
        log = AfddLog()
        log.info("step1")
        dbg = debug_payload(log, stage="done", n=3)
        self.assertEqual(dbg["stage"], "done")
        self.assertEqual(dbg["n"], 3)
        self.assertIn("step1", dbg["server_log"])

    def test_chunked_records_eval_error(self) -> None:
        now_ms = int(time.time() * 1000)
        base = now_ms - 10 * 3600_000

        def fetch_interval(start_ms: int, end_ms_exclusive: int) -> list[dict]:
            out = []
            t = max(start_ms, base)
            i = 0
            while t < end_ms_exclusive and t < now_ms:
                out.append({"ts_ms": t, "degF": 70.0, "degC": 21.0, "seq": i})
                t += 120_000
                i += 1
            return out

        rules = [
            {
                "id": "boom_rule",
                "enabled": True,
                "config": {},
                "code": """def evaluate(row, cfg, prev_row=None, rows=None):
    if row["row"] == 3:
        raise RuntimeError("boom")
    return False
""",
            }
        ]
        summary = chunked_evaluate_custom_rules(
            rules=rules,
            lookback_hours=10,
            fetch_interval=fetch_interval,
            chunk_hours=4,
        )
        self.assertGreater(summary.get("chunk_count", 0), 0)
        errs = summary.get("chunk_errors") or []
        self.assertTrue(errs)
        self.assertTrue(any("eval failed" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
