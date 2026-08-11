"""Peak-day shape gallery helpers."""

from pathlib import Path

import numpy as np
import pandas as pd

from peak_day_shape_gallery import find_peak_demand_day, load_meter_demand, meter_hourly_kw


def test_find_peak_demand_day_matches_max_kw(tmp_path: Path):
    rows = []
    # 2026-01-10 quiet, 2026-01-26 has the spike
    for day, peak in [("2026-01-10", 100.0), ("2026-01-26", 330.0)]:
        for h in range(24):
            for q in range(4):
                ts = pd.Timestamp(f"{day} {h:02d}:{q*15:02d}:00", tz="UTC")
                kw = peak if (day == "2026-01-26" and h == 13 and q == 0) else 50.0
                rows.append({"timestamp_utc": ts.isoformat().replace("+00:00", "Z"), "kw_demand": kw})
    csv = tmp_path / "meter.csv"
    pd.DataFrame(rows).to_csv(csv, index=False)
    demand = load_meter_demand(csv)
    day, peak_kw, _ = find_peak_demand_day(demand)
    assert day == "2026-01-26"
    assert peak_kw == 330.0
    hourly = meter_hourly_kw(demand, day)
    assert hourly is not None
    assert len(hourly) == 24
    assert np.nanmax(hourly) >= 50.0


def test_eplus_best_weather_match_picks_closer_oat(tmp_path: Path):
    from peak_day_shape_gallery import eplus_best_weather_match

    rows = []
    for day, oat0 in [("2026-01-05", 10.0), ("2026-01-11", 25.0)]:
        for h in range(24):
            for q in range(4):
                rows.append(
                    {
                        "day": day,
                        "hour_ending": h,
                        "minute": q * 15,
                        "quarter_index": h * 4 + q,
                        "facility_kw": 100.0 + h,
                        "oat_f": oat0 + 0.2 * h,
                        "control_regime": "baseline",
                        "is_weekend": False,
                    }
                )
    pq = tmp_path / "paired.parquet"
    pd.DataFrame(rows).to_parquet(pq)
    query = np.array([10.0 + 0.2 * h for h in range(24)])
    match = eplus_best_weather_match(pq, query, prefer_weekend=False)
    assert match is not None
    assert match[0] == "2026-01-05"
    assert match[2] < 1.0
