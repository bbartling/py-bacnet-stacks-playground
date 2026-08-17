"""EnergyPlus W2A warning phase parser: real total/warmup/sizing block."""
from __future__ import annotations

from pathlib import Path

import pytest

from eplus_gym.eplus_err import assert_eplus_quality, parse_eplus_err, scored_runtime_w2a_count
from eplus_gym.trackb_banks import scored_runtime_w2a_pass

REAL_BLOCK = (
    "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of "
    "water-to-air heat pump coil rated air flow rate.\n"
    "*************  **   ~~~   **  This error occurred 46152 total times;\n"
    "*************  **   ~~~   **  during Warmup 39052 times;\n"
    "*************  **   ~~~   **  during Sizing 0 times.\n"
    "************* EnergyPlus Completed Successfully-- 1 Warning; 0 Severe Errors\n"
)


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "eplusout.err"
    p.write_text(text, encoding="utf-8")
    return p


def test_real_46152_block_runtime_7100(tmp_path):
    gate = parse_eplus_err(_write(tmp_path, REAL_BLOCK))
    phase = gate["w2a_low_airflow_by_phase"]
    assert phase["warmup"] == 39052
    assert phase["sizing"] == 0
    assert phase["scored_runtime"] == 7100
    assert gate["recurring"]["w2a_low_airflow"] == 46152
    assert gate["w2a_phase_unparseable"] is False
    assert scored_runtime_w2a_count(gate) == 7100
    assert scored_runtime_w2a_pass(gate) is False


def test_warmup_only(tmp_path):
    text = (
        "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of water-to-air heat pump coil rated air flow rate.\n"
        "*************  **   ~~~   **  This error occurred 12 total times;\n"
        "*************  **   ~~~   **  during Warmup 12 times;\n"
        "*************  **   ~~~   **  during Sizing 0 times.\n"
        "************* EnergyPlus Completed Successfully-- 1 Warning; 0 Severe Errors\n"
    )
    gate = parse_eplus_err(_write(tmp_path, text))
    assert gate["w2a_low_airflow_by_phase"]["warmup"] == 12
    assert gate["w2a_low_airflow_by_phase"]["scored_runtime"] == 0
    assert scored_runtime_w2a_pass(gate) is True


def test_sizing_only(tmp_path):
    text = (
        "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of water-to-air heat pump coil rated air flow rate.\n"
        "*************  **   ~~~   **  This error occurred 8 total times;\n"
        "*************  **   ~~~   **  during Warmup 0 times;\n"
        "*************  **   ~~~   **  during Sizing 8 times.\n"
        "************* EnergyPlus Completed Successfully-- 1 Warning; 0 Severe Errors\n"
    )
    gate = parse_eplus_err(_write(tmp_path, text))
    assert gate["w2a_low_airflow_by_phase"]["sizing"] == 8
    assert gate["w2a_low_airflow_by_phase"]["scored_runtime"] == 0
    assert scored_runtime_w2a_pass(gate) is True


def test_mixed_and_multi_block(tmp_path):
    text = (
        "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of water-to-air heat pump coil rated air flow rate.\n"
        "*************  **   ~~~   **  This error occurred 10 total times;\n"
        "*************  **   ~~~   **  during Warmup 6 times;\n"
        "*************  **   ~~~   **  during Sizing 1 times.\n"
        "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of water-to-air heat pump coil rated air flow rate.\n"
        "*************  **   ~~~   **  This error occurred 5 total times;\n"
        "*************  **   ~~~   **  during Warmup 0 times;\n"
        "*************  **   ~~~   **  during Sizing 0 times.\n"
        "************* EnergyPlus Completed Successfully-- 2 Warning; 0 Severe Errors\n"
    )
    gate = parse_eplus_err(_write(tmp_path, text))
    phase = gate["w2a_low_airflow_by_phase"]
    assert phase["warmup"] == 6
    assert phase["sizing"] == 1
    assert phase["scored_runtime"] == 8  # (10-6-1) + (5-0-0)
    assert scored_runtime_w2a_pass(gate) is False


def test_total_lt_warmup_plus_sizing_fail_closed(tmp_path):
    text = (
        "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of water-to-air heat pump coil rated air flow rate.\n"
        "*************  **   ~~~   **  This error occurred 5 total times;\n"
        "*************  **   ~~~   **  during Warmup 4 times;\n"
        "*************  **   ~~~   **  during Sizing 3 times.\n"
        "************* EnergyPlus Completed Successfully-- 1 Warning; 0 Severe Errors\n"
    )
    gate = parse_eplus_err(_write(tmp_path, text))
    assert gate["w2a_phase_fail_closed"] is True
    assert scored_runtime_w2a_count(gate) is None
    with pytest.raises(ValueError, match="unparseable"):
        assert_eplus_quality(gate, max_scored_runtime_w2a=0)


def test_missing_and_malformed_fail_closed(tmp_path):
    text = (
        "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of water-to-air heat pump coil rated air flow rate.\n"
        "*************  **   ~~~   **  This error occurred 954 total times;\n"
        "************* EnergyPlus Completed Successfully-- 10 Warning; 0 Severe Errors\n"
    )
    gate = parse_eplus_err(_write(tmp_path, text))
    assert gate["w2a_phase_unparseable"] is True
    assert scored_runtime_w2a_pass(gate) is False
    with pytest.raises(ValueError, match="unparseable"):
        assert_eplus_quality(gate, max_scored_runtime_w2a=0)
