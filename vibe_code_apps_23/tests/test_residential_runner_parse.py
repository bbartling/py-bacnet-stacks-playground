"""Interval-count safety for the residential eplusout.csv parser.

The J→kW divisor hard-codes a 5-minute reporting interval, so an hourly CSV parsed as if
it were 5-minute data overstates kW / kWh / $ by 12×. These tests pin the loud failure.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from vibe23.residential.constants import DT_HOURS, INTERVALS_PER_DAY
from vibe23.residential.runner import _require_288, parse_eplus_csv

FACILITY_COL = "Electricity:Facility [J](TimeStep)"
ZONE_COL = "ZONE ONE:Zone Mean Air Temperature [C](TimeStep)"


def _write_csv(run_dir: Path, rows: int, *, kw: float = 2.4, zone_c: float = 22.0) -> Path:
    """Write an eplusout.csv with ``rows`` data rows at a constant power draw."""
    run_dir.mkdir(parents=True, exist_ok=True)
    joules = kw * DT_HOURS * 3_600_000.0
    lines = [f"Date/Time,{FACILITY_COL},{ZONE_COL}"]
    for i in range(rows):
        lines.append(f" 07/15  {i:02d}:00:00,{joules},{zone_c}")
    path = run_dir / "eplusout.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_parse_288_rows_converts_joules_to_kw(tmp_path: Path) -> None:
    _write_csv(tmp_path / "run", INTERVALS_PER_DAY, kw=2.4, zone_c=22.0)
    parsed = parse_eplus_csv(tmp_path / "run")
    assert len(parsed.index) == INTERVALS_PER_DAY
    assert parsed["facility_kw"].iloc[0] == pytest.approx(2.4)
    assert parsed["zone_temp_f"].iloc[0] == pytest.approx(71.6)
    day_kwh = float(parsed["facility_kw"].sum()) * DT_HOURS
    assert day_kwh == pytest.approx(2.4 * 24.0)


def test_parse_hourly_24_rows_raises(tmp_path: Path) -> None:
    _write_csv(tmp_path / "hourly", 24)
    with pytest.raises(ValueError, match="hourly"):
        parse_eplus_csv(tmp_path / "hourly")


@pytest.mark.parametrize("rows", [1, 96, 144, 287, 289, 576])
def test_parse_wrong_length_raises(tmp_path: Path, rows: int) -> None:
    run_dir = tmp_path / f"rows_{rows}"
    _write_csv(run_dir, rows)
    with pytest.raises(ValueError, match=f"expected exactly {INTERVALS_PER_DAY}"):
        parse_eplus_csv(run_dir)


def test_parse_missing_csv_raises(tmp_path: Path) -> None:
    (tmp_path / "empty_run").mkdir()
    with pytest.raises(FileNotFoundError):
        parse_eplus_csv(tmp_path / "empty_run")


def test_require_288_does_not_pad_or_truncate() -> None:
    exact = [1.0] * INTERVALS_PER_DAY
    assert _require_288(exact, label="facility_kw") == exact
    for bad in ([], [1.0] * 24, [1.0] * 287, [1.0] * 289):
        with pytest.raises(ValueError, match=f"expected exactly {INTERVALS_PER_DAY}"):
            _require_288(bad, label="facility_kw")
