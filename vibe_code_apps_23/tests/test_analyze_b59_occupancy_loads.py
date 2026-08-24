from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


def _module():
    path = Path(__file__).parents[1] / "scripts" / "analyze_b59_occupancy_loads.py"
    spec = importlib.util.spec_from_file_location("analyze_b59_occupancy_loads", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_fixture(root: Path) -> None:
    pd.DataFrame(
        [
            ["2018-07-03 07:00:00", 1, 2],
            ["2018-07-03 08:00:00", 3, 4],
            ["2018-07-04 08:00:00", 5, 6],
            ["2020-03-18 08:00:00", 0, 0],
        ],
        columns=["date", "occ_third_south", "occ_fourth_south"],
    ).to_csv(root / "occ.csv", index=False)
    pd.DataFrame(
        [
            ["2018/7/3 07:00", 1, 1, 10, 20],
            ["2018/7/3 08:00", 1, 1, 20, 30],
            ["2018/7/4 08:00", 1, 1, 20, 30],
            ["2020/3/18 08:00", 1, 1, 3, 4],
            ["2020/3/18 08:00", 1, 1, 3, 4],
        ],
        columns=["date", "wifi_first_south", "wifi_second_south", "wifi_third_south", "wifi_fourth_south"],
    ).to_csv(root / "wifi.csv", index=False)
    pd.DataFrame(
        [
            ["2018/7/3 07:00", 5, 2, 10],
            ["2018/7/3 08:00", 6, 4, 11],
            ["2018/7/4 08:00", 6, 4, 11],
            ["2020/3/18 08:00", 1, 0.4, 2],
        ],
        columns=["date", "mels_S", "lig_S", "mels_N"],
    ).to_csv(root / "ele.csv", index=False)


def test_build_evidence_preserves_hashes_scope_and_non_claim_boundary(tmp_path):
    _write_fixture(tmp_path)
    evidence = _module().build_evidence(tmp_path)

    assert evidence["claim_status"] == "DIAGNOSTIC_EVIDENCE_AND_BOUNDED_PRIORS_ONLY"
    assert evidence["source_data"]["occupancy_camera"]["sha256"]
    assert evidence["source_data"]["wifi"]["duplicate_timestamp_rows"] == 2
    assert "not a whole-office population" in evidence["source_data"]["occupancy_camera"]["unit"]
    assert evidence["profiles"]["camera_south_office_sum"]["hourly_median_by_source_day_type"]["us_federal_holiday"][8] == 11.0
    assert evidence["profiles"]["wifi_south_office_sum"]["ambiguous_duplicate_rows_excluded"] == 2
    assert evidence["pandemic_regime_daily_median_kw_or_count"]["mels_total_kw"]["2020_shelter_in_place_from_2020_03_18"] == 3.0
    assert any("lig_S" in item for item in evidence["modeling_constraints"])


def test_cli_writes_only_derived_json(tmp_path, monkeypatch):
    _write_fixture(tmp_path)
    output = tmp_path / "result" / "evidence.json"
    module = _module()
    monkeypatch.setattr("sys.argv", ["analyze", "--raw-root", str(tmp_path), "--output", str(output)])

    assert module.main() == 0
    assert output.is_file()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["ele.csv", "occ.csv", "result", "wifi.csv"]
