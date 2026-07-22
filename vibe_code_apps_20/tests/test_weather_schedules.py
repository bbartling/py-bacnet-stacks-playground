"""Tests for weather-responsive availability schedules + Schedule:File patch."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from wattlab.energyplus.patches.weather_schedules import apply_weather_schedule_file
from wattlab.existing_building.schedules import (
    STRATEGIES,
    build_strategy_series,
    build_weather_schedule,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "examples" / "prototypes" / "5ZoneAirCooled.idf"

CONFIG = {
    "occupied": {
        "monday_friday": ["07:00", "17:00"],
        "saturday": ["08:00", "12:00"],
        "sunday": None,
    },
    "weather_extensions": {
        "hot": {
            "outdoor_air_threshold_f": 88.0,
            "early_start_hours": 2,
            "late_stop_hours": 2,
            "allow_overnight": False,
        },
        "cold": {
            "outdoor_air_threshold_f": 15.0,
            "early_start_hours": 3,
            "late_stop_hours": 3,
            "allow_overnight": True,
        },
    },
}


def _series(
    start: datetime,
    end: datetime,
    default_f: float = 70.0,
    overrides: dict[datetime, float] | None = None,
) -> list[tuple[datetime, float]]:
    """Contiguous hourly OAT series over [start, end] inclusive."""
    overrides = overrides or {}
    out: list[tuple[datetime, float]] = []
    t = start
    while t <= end:
        out.append((t, overrides.get(t, default_f)))
        t += timedelta(hours=1)
    return out


def _idx(start: datetime, when: datetime) -> int:
    return int((when - start).total_seconds() // 3600)


# ---------------------------------------------------------------------------
# Hot threshold only extends hot hours
# ---------------------------------------------------------------------------

def test_hot_threshold_only_extends_hot_hours() -> None:
    start = datetime(2025, 1, 1)
    end = datetime(2025, 12, 31, 23)
    # 2025-06-10 is a Tuesday (occupied 07:00-17:00, early-start lead 05:00-06:00).
    overrides = {
        datetime(2025, 6, 10, 5): 95.0,   # hot, inside 2 h lead -> on
        datetime(2025, 6, 10, 6): 92.0,   # hot, inside 2 h lead -> on
        datetime(2025, 6, 10, 4): 95.0,   # hot, but OUTSIDE the 2 h lead -> off
        datetime(2025, 6, 12, 6): 5.0,    # cold, hot strategy must ignore -> off
    }
    series = _series(start, end, overrides=overrides)

    base = build_strategy_series("normal_fixed", series, CONFIG)
    values = build_strategy_series("hot_early_start", series, CONFIG)

    assert values[_idx(start, datetime(2025, 6, 10, 5))] == 1
    assert values[_idx(start, datetime(2025, 6, 10, 6))] == 1
    assert values[_idx(start, datetime(2025, 6, 10, 4))] == 0
    assert values[_idx(start, datetime(2025, 6, 12, 6))] == 0

    # Every added hour must itself be a hot hour: the extension is applied
    # hour-by-hour, never as a year-long stretch of longer operation.
    added = [i for i, (b, v) in enumerate(zip(base, values)) if v and not b]
    assert added == [
        _idx(start, datetime(2025, 6, 10, 5)),
        _idx(start, datetime(2025, 6, 10, 6)),
    ]
    assert all(series[i][1] >= 88.0 for i in added)


# ---------------------------------------------------------------------------
# Leap year
# ---------------------------------------------------------------------------

def test_leap_year_series_and_csv(tmp_path: Path) -> None:
    start = datetime(2024, 1, 1)
    end = datetime(2024, 12, 31, 23)
    series = _series(start, end)
    assert len(series) == 8784

    values = build_strategy_series("normal_fixed", series, CONFIG)
    # 2024-02-29 is a Thursday: occupied at 10:00, closed at 03:00.
    assert values[_idx(start, datetime(2024, 2, 29, 10))] == 1
    assert values[_idx(start, datetime(2024, 2, 29, 3))] == 0

    dest = tmp_path / "avail_2024.csv"
    meta = build_weather_schedule("normal_fixed", series, CONFIG, dest)
    assert meta["rows"] == 8784
    assert meta["leap_year"] is True
    assert meta["full_year"] is True
    assert meta["tz"] == "local_standard_assumed"
    assert len(meta["source_sha256"]) == 64
    assert len(dest.read_text(encoding="utf-8").splitlines()) == 8785  # header + rows


# ---------------------------------------------------------------------------
# Cold overnight
# ---------------------------------------------------------------------------

def test_cold_overnight_extreme_respects_allow_overnight() -> None:
    start = datetime(2025, 1, 1)
    end = datetime(2025, 12, 31, 23)
    cold_night = [
        datetime(2025, 1, 15, 22),  # Wednesday night
        datetime(2025, 1, 15, 23),
        datetime(2025, 1, 16, 0),
        datetime(2025, 1, 16, 1),
    ]
    overrides: dict[datetime, float] = {t: 0.0 for t in cold_night}
    # Hot overnight hour, but hot.allow_overnight is False -> must stay off.
    overrides[datetime(2025, 7, 15, 23)] = 95.0
    series = _series(start, end, overrides=overrides)

    values = build_strategy_series("overnight_extreme", series, CONFIG)
    for t in cold_night:
        assert values[_idx(start, t)] == 1, t
    assert values[_idx(start, datetime(2025, 7, 15, 23))] == 0

    # Same cold snap with allow_overnight disabled -> nothing turns on.
    config_no_overnight = copy.deepcopy(CONFIG)
    config_no_overnight["weather_extensions"]["cold"]["allow_overnight"] = False
    values_off = build_strategy_series("overnight_extreme", series, config_no_overnight)
    for t in cold_night:
        assert values_off[_idx(start, t)] == 0, t


# ---------------------------------------------------------------------------
# Cross-year windows
# ---------------------------------------------------------------------------

def test_cold_late_stop_crosses_midnight_and_year_boundary() -> None:
    config = copy.deepcopy(CONFIG)
    config["occupied"]["monday_friday"] = ["15:00", "23:00"]
    start = datetime(2025, 12, 29)
    end = datetime(2026, 1, 4, 23)
    # 2025-12-31 is a Wednesday; last occupied hour is 22:00, lag hours are
    # 23:00 (same day), 00:00 and 01:00 (New Year's Day 2026).
    overrides = {
        datetime(2025, 12, 31, 23): 0.0,
        datetime(2026, 1, 1, 0): 0.0,
        datetime(2026, 1, 1, 1): 20.0,  # not cold -> off
    }
    series = _series(start, end, overrides=overrides)

    values = build_strategy_series("cold_late_stop", series, config)
    assert values[_idx(start, datetime(2025, 12, 31, 23))] == 1
    assert values[_idx(start, datetime(2026, 1, 1, 0))] == 1
    assert values[_idx(start, datetime(2026, 1, 1, 1))] == 0

    # allow_overnight=False stops the extension at the midnight/year boundary.
    config_no_overnight = copy.deepcopy(config)
    config_no_overnight["weather_extensions"]["cold"]["allow_overnight"] = False
    values_clamped = build_strategy_series("cold_late_stop", series, config_no_overnight)
    assert values_clamped[_idx(start, datetime(2025, 12, 31, 23))] == 1
    assert values_clamped[_idx(start, datetime(2026, 1, 1, 0))] == 0


# ---------------------------------------------------------------------------
# Strategy grid sanity
# ---------------------------------------------------------------------------

def test_every_strategy_builds_a_valid_series() -> None:
    start = datetime(2025, 6, 9)  # Monday
    end = datetime(2025, 6, 15, 23)  # Sunday
    overrides = {
        datetime(2025, 6, 10, 6): 95.0,
        datetime(2025, 6, 14, 13): 96.0,  # Saturday afternoon extreme
        datetime(2025, 6, 11, 2): 5.0,    # cold overnight hour
    }
    series = _series(start, end, overrides=overrides)
    base = build_strategy_series("normal_fixed", series, CONFIG)
    manual = [{"start": "2025-06-11T19:00", "end": "2025-06-11T22:00"}]

    for strategy in STRATEGIES:
        values = build_strategy_series(
            strategy, series, CONFIG, manual_overrides=manual
        )
        assert len(values) == len(series)
        assert set(values) <= {0, 1}
        # Strategies only ever ADD hours on top of the base occupancy.
        assert all(v >= b for v, b in zip(values, base)), strategy

    manual_values = build_strategy_series(
        "manual_override", series, CONFIG, manual_overrides=manual
    )
    for hour in (19, 20, 21):
        assert manual_values[_idx(start, datetime(2025, 6, 11, hour))] == 1
    assert manual_values[_idx(start, datetime(2025, 6, 11, 22))] == 0


def test_unknown_strategy_and_gappy_series_raise() -> None:
    series = _series(datetime(2025, 6, 9), datetime(2025, 6, 9, 23))
    with pytest.raises(ValueError, match="Unknown schedule strategy"):
        build_strategy_series("no_such_strategy", series, CONFIG)
    gappy = [series[0], series[5]]
    with pytest.raises(ValueError, match="contiguous hourly"):
        build_strategy_series("normal_fixed", gappy, CONFIG)


# ---------------------------------------------------------------------------
# Schedule:File IDF patch
# ---------------------------------------------------------------------------

def _annual_csv(tmp_path: Path) -> tuple[Path, dict]:
    series = _series(datetime(2025, 1, 1), datetime(2025, 12, 31, 23))
    dest = tmp_path / "avail.csv"
    meta = build_weather_schedule(
        "normal_fixed", series, CONFIG, dest, schedule_name="WattLab Weather Avail"
    )
    return dest, meta


def test_patch_repoints_fan_availability_on_prototype(tmp_path: Path) -> None:
    csv_path, sched_meta = _annual_csv(tmp_path)
    dest = tmp_path / "patched.idf"
    meta = apply_weather_schedule_file(
        PROTOTYPE, dest, csv_path, "WattLab Weather Avail"
    )
    assert meta["ok"] is True
    assert meta["patch"] == "weather_schedule_file"
    assert meta["references_repointed"] >= 2  # AvailabilityManager + supply fan
    assert meta["surrogate"] is None
    assert meta["csv_rows"] == 8760
    assert meta["csv_sha256"] == sched_meta["source_sha256"]

    text = dest.read_text(encoding="utf-8")
    assert "Schedule:File," in text
    assert "WattLab Weather Avail" in text
    assert "/work/in/avail.csv" in text
    assert (tmp_path / "avail.csv").is_file()  # sidecar beside patched IDF
    # No fan availability reference still points at the old compact schedule.
    assert "FanAvailSched;           !- Schedule Name" not in text
    assert "FanAvailSched,           !- Availability Schedule Name" not in text
    # The original schedule definition itself is left in place.
    assert "FanAvailSched,           !- Name" in text


def test_patch_dind_stages_csv_into_work_in(tmp_path: Path) -> None:
    """BUG-W-SCHEDULE-FILE-DIND: CSV staged next to IDF for /work/in mount."""
    from wattlab.energyplus.docker import ensure_ep_writable, _chmod_loose
    from wattlab.energyplus.patches.weather_schedules import (
        schedule_file_basenames_in_idf,
    )
    import shutil

    csv_path, _ = _annual_csv(tmp_path)
    work = tmp_path / "sim_out"
    work.mkdir()
    dest = work / "patched.idf"
    apply_weather_schedule_file(PROTOTYPE, dest, csv_path, "WattLab Weather Avail")
    text = dest.read_text(encoding="utf-8")
    assert schedule_file_basenames_in_idf(text) == ["avail.csv"]
    assert (work / "avail.csv").is_file()

    stage = work.parent / f"{work.name}__stage_in"
    ensure_ep_writable(stage)
    shutil.copy2(dest, stage / dest.name)
    for base in schedule_file_basenames_in_idf(text):
        src_csv = dest.parent / base
        assert src_csv.is_file()
        shutil.copy2(src_csv, stage / base)
        _chmod_loose(stage / base)
    assert (stage / "avail.csv").is_file()
    assert (stage / "avail.csv").read_bytes() == csv_path.read_bytes()


def test_patch_reapply_is_idempotent(tmp_path: Path) -> None:
    csv_path, _ = _annual_csv(tmp_path)
    first = tmp_path / "first.idf"
    second = tmp_path / "second.idf"
    apply_weather_schedule_file(PROTOTYPE, first, csv_path, "WattLab Weather Avail")
    meta = apply_weather_schedule_file(first, second, csv_path, "WattLab Weather Avail")

    text = second.read_text(encoding="utf-8")
    assert text.count("WattLab Weather Avail,  !- Name") == 1
    # References were already repointed on the first pass; the surrogate note
    # documents that no FanAvailSched reference remained to rewire.
    assert meta["references_repointed"] == 0
    assert meta["surrogate"] is not None


def test_patch_documents_surrogate_when_no_fan_reference(tmp_path: Path) -> None:
    csv_path, _ = _annual_csv(tmp_path)
    bare = tmp_path / "bare.idf"
    bare.write_text("Version,26.1;\n", encoding="utf-8")
    dest = tmp_path / "bare_patched.idf"
    meta = apply_weather_schedule_file(bare, dest, csv_path, "WattLab Weather Avail")
    assert meta["ok"] is True
    assert meta["references_repointed"] == 0
    assert "manual" in meta["surrogate"]
    assert (
        "fan_availability_reference_not_found_surrogate_documented" in meta["flags"]
    )
    assert "Schedule:File," in dest.read_text(encoding="utf-8")


def test_patch_missing_csv_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="schedule_csv does not exist"):
        apply_weather_schedule_file(
            PROTOTYPE, tmp_path / "x.idf", tmp_path / "nope.csv", "X"
        )
