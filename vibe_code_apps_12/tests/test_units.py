"""Temperature unit helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import prepare_rows_for_evaluate, readings_to_rows, sweep_rule  # noqa: E402
from units import (  # noqa: E402
    f_to_c,
    resolve_cfg_threshold,
    temp_from_row,
    temp_unit_symbol,
)


class TestUnits(unittest.TestCase):
    def test_legacy_f_config_imperial(self) -> None:
        cfg = {"bounds_low_f": 65.0}
        self.assertEqual(resolve_cfg_threshold(cfg, "bounds_low", "imperial"), 65.0)

    def test_legacy_f_converts_for_metric_rule(self) -> None:
        cfg = {"bounds_low_f": 32.0}
        self.assertAlmostEqual(
            resolve_cfg_threshold(cfg, "bounds_low", "metric"), 0.0, places=2
        )

    def test_row_temp_fields_metric(self) -> None:
        rows = readings_to_rows([{"ts_ms": 1_000_000, "degF": 32.0, "degC": 0.0}])
        prepare_rows_for_evaluate(rows, 1, temp_unit="metric")
        self.assertAlmostEqual(rows[0]["temp"], 0.0, places=2)
        self.assertEqual(temp_unit_symbol("metric"), "°C")

    def test_sweep_uses_temp_in_rule_unit(self) -> None:
        readings = [{"ts_ms": 1_000_000 + i * 10_000, "degF": 90.0, "degC": 32.2} for i in range(5)]
        rows = readings_to_rows(readings)
        code = """def evaluate(row, cfg, prev_row=None, rows=None):
    return row["temp"] > cfg_threshold(cfg, "bounds_high")
"""
        cfg = {"bounds_high": 30.0, "temp_unit": "metric"}
        flags, _ = sweep_rule(code, cfg, rows, capture_print=False)
        self.assertGreater(sum(flags), 0)


if __name__ == "__main__":
    unittest.main()
