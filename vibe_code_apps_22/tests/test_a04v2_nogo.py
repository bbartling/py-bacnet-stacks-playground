"""A04-v2 development contracts: hygiene, peak windows, fail-closed provenance."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "scripts"))

from a04v2_phase0_freeze import Phase0Error, freeze_baseline
from a04v2_phase2_zone_dataset import contiguous_abs_delta
from eplus_gym.a04_identity import A04_SHA_ALLOWED, A04_SHA_LF, CAPMULT_HI, assert_finite_in_range, is_a04_idf_filename
from eplus_gym.a04v2_selection import (
    STATUS_RAMP_PASS_WARNING_FAIL,
    VERDICT_INCOMPLETE,
    VERDICT_NOGO,
    classify_stage_b_status,
    compute_selection_verdict,
    track_b_state_from_plan,
)
from eplus_gym.demand_windows import demand_window_report, freeze_peak_contract
from eplus_gym.eplus_err import assert_eplus_quality
from eplus_gym.envs.lakeside_w2a import is_a04_idf_filename as env_is_a04
from eplus_gym.objective import BAS_ZONE_COLS
from eplus_gym.ramp_artifact import RampArtifactError, canonical_ramp_gate_path, resolve_ramp_artifact_dest
from eplus_gym.rl.operator_pay_experiment import refuse_full_campaign, write_smoke_plots
from eplus_gym.rl.physics_ramp_gate import ENGINEERING_MARGIN, abs_15min_deltas
from eplus_gym.site_env import SiteRootError, require_site_root
from eplus_gym.site_pins import sha256_file


def test_a04_hash_immutable():
    idf = APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    digest = hashlib.sha256(idf.read_bytes()).hexdigest()
    assert digest in A04_SHA_ALLOWED
    lf = idf.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    assert hashlib.sha256(lf).hexdigest() == A04_SHA_LF


def test_engineering_margin_unchanged():
    assert ENGINEERING_MARGIN == 3.0


def test_refuse_full_while_committed_ramp_failed():
    decision = refuse_full_campaign(APP)
    assert decision["allowed"] is False


def test_a04v2_filename_allowlist():
    assert is_a04_idf_filename("lakeside_w2a_a04v2_capmult_t28.idf")
    assert is_a04_idf_filename("staged_lakeside_w2a_a04v2_capmult_t28.idf")
    assert is_a04_idf_filename("lakeside_w2a_a04_dual_champion.idf")
    assert is_a04_idf_filename("staged_lakeside_w2a_a04_dual_champion.idf")
    assert not is_a04_idf_filename("random_building.idf")
    assert not is_a04_idf_filename("unreviewed_lakeside_w2a_a04_dual_champion.idf")
    assert env_is_a04("lakeside_w2a_a04v2_x.idf")
    assert not env_is_a04("unreviewed_lakeside_w2a_a04_dual_champion.idf")


def test_candidate_cannot_overwrite_canonical_ramp_gate(tmp_path: Path):
    app = tmp_path
    (app / "docs" / "audits" / "figures" / "postfix").mkdir(parents=True)
    canonical = canonical_ramp_gate_path(app)
    canonical.write_text("{}\n", encoding="utf-8")
    out = tmp_path / "cand"
    dest = resolve_ramp_artifact_dest(
        app_root=app,
        out=out,
        write_artifact=None,
        idf=Path("lakeside_w2a_a04v2_capmult_t28.idf"),
    )
    assert dest == out / "ramp_gate.json"
    with pytest.raises(RampArtifactError):
        resolve_ramp_artifact_dest(
            app_root=app,
            out=out,
            write_artifact=canonical,
            idf=Path("lakeside_w2a_a04v2_capmult_t28.idf"),
        )


def test_bas_gap_mode_requires_sorted_unique_index():
    idx = pd.to_datetime(["2026-01-01 00:15", "2026-01-01 00:00"])
    frame = pd.DataFrame({c: [70.0, 71.0] for c in BAS_ZONE_COLS}, index=idx)
    with pytest.raises(ValueError, match="unique and monotonic"):
        abs_15min_deltas(frame, require_contiguous=False)


def test_contiguous_dt_ignores_gaps():
    stamps = pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:15", "2026-01-01 01:00"])
    temps = pd.Series([70.0, 71.0, 80.0])
    d = contiguous_abs_delta(temps, pd.Series(stamps))
    assert d.iloc[1] == pytest.approx(1.0)
    assert pd.isna(d.iloc[2])


def test_capmult_bounds():
    assert_finite_in_range(28.0, lo=1.0, hi=CAPMULT_HI, name="temp-mult")
    with pytest.raises(ValueError):
        assert_finite_in_range(float("nan"), lo=1.0, hi=80.0, name="temp-mult")
    with pytest.raises(ValueError):
        assert_finite_in_range(-1.0, lo=0.0, hi=5000.0, name="area-m2")
    with pytest.raises(ValueError):
        assert_finite_in_range(9000.0, lo=0.0, hi=5000.0, name="area-m2")


def test_empty_site_root_rejected(monkeypatch):
    monkeypatch.delenv("SITE_ROOT", raising=False)
    with pytest.raises(SiteRootError):
        require_site_root("")
    with pytest.raises(SiteRootError):
        require_site_root(None, env={})


def test_phase0_missing_epw_fails(tmp_path: Path):
    app = tmp_path / "app"
    (app / "models" / "eplus").mkdir(parents=True)
    (app / "docs" / "audits" / "figures" / "postfix").mkdir(parents=True)
    src = APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    (app / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf").write_bytes(src.read_bytes())
    (app / "docs" / "audits" / "figures" / "postfix" / "ramp_gate.json").write_text(
        json.dumps({"passed": False, "threshold_f_per_15min": 2.65}), encoding="utf-8"
    )
    site = tmp_path / "site"
    site.mkdir()
    with pytest.raises(Phase0Error, match="EPW missing"):
        freeze_baseline(app=app, site=site)


def test_skip_eplus_plots_without_rows(tmp_path: Path):
    written = write_smoke_plots(tmp_path, rows=[])
    assert written
    assert not (tmp_path / "03-arm-scorecard.png").exists()


def test_w2a_warning_gate_fails_when_bound_set():
    gate = {
        "completed_successfully": True,
        "fatal_count": 0,
        "severe_count": 0,
        "recurring": {"w2a_low_airflow": 12},
    }
    assert_eplus_quality(gate)
    with pytest.raises(ValueError, match="low-airflow"):
        assert_eplus_quality(gate, max_w2a_low_airflow=0)


def test_parse_eplus_err_uses_occurred_total_times(tmp_path: Path):
    from eplus_gym.eplus_err import parse_eplus_err

    err = tmp_path / "eplusout.err"
    err.write_text(
        "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of water-to-air heat pump coil rated air flow rate.\n"
        "*************  **   ~~~   **   This error occurred 954 total times;\n"
        "************* EnergyPlus Completed Successfully-- 10 Warning; 0 Severe Errors\n",
        encoding="utf-8",
    )
    gate = parse_eplus_err(err)
    assert gate["recurring"]["w2a_low_airflow"] == 954


def test_demand_windows_same_for_bas_and_eplus():
    idx = pd.date_range("2026-01-26", periods=8, freq="15min")
    s = pd.Series([100, 200, 300, 280, 260, 240, 220, 200], index=idx, dtype=float)
    rep = demand_window_report(s, native_minutes=15)
    assert rep["hard_gate"] is False
    assert rep["aligned_max_kw"]["15"]["end"] == pytest.approx(300.0)
    assert rep["aligned_max_kw"]["30"]["end"] is not None
    assert freeze_peak_contract()["hard_gate_on_15min_vs_billed"] is False
    assert freeze_peak_contract()["legacy_250_290"]["enforced_in_a04v2_selection"] is False


def test_sub_native_demand_windows_unavailable_or_rejected():
    from eplus_gym.demand_windows import resample_mean, rolling_mean

    idx = pd.date_range("2026-01-26", periods=8, freq="15min")
    s = pd.Series([100, 200, 300, 280, 260, 240, 220, 200], index=idx, dtype=float)
    rep = demand_window_report(s, native_minutes=15)
    assert 5 in rep["unavailable_windows_min"]
    assert rep["aligned_max_kw"]["5"]["end"] is None
    assert rep["aligned_max_kw"]["5"]["start"] is None
    assert rep["rolling_max_kw"]["5"] is None
    assert rep["aligned_max_kw"]["15"]["end"] == pytest.approx(300.0)
    assert rep["aligned_max_kw"]["30"]["end"] is not None
    assert rep["aligned_max_kw"]["60"]["end"] is not None
    with pytest.raises(ValueError, match="sub-native"):
        resample_mean(s, 5, native_minutes=15)
    with pytest.raises(ValueError, match="sub-native"):
        rolling_mean(s, 5, native_minutes=15)
    fine = pd.date_range("2026-01-26", periods=12, freq="5min")
    fine_s = pd.Series(range(12), index=fine, dtype=float)
    ok = demand_window_report(fine_s, native_minutes=5)
    assert ok["unavailable_windows_min"] == []
    assert ok["aligned_max_kw"]["5"]["end"] is not None


def test_selection_verdict_is_computed_not_hand_copied():
    body = compute_selection_verdict(
        stage_a_summary={"trials": 8},
        peak_contract=freeze_peak_contract(),
        champion=None,
    )
    assert body["verdict"] == VERDICT_INCOMPLETE
    assert body["long_campaign_allowed"] is False
    assert body["champion"] is None
    assert body["track_b_planned"] is False
    assert body["track_b_executed"] is False
    assert body["track_b_completed"] is False
    assert body["track_b_failed_honestly"] is False
    assert body["ramp_threshold_unchanged"]["engineering_margin"] == 3.0


def test_track_b_plan_file_is_not_executed():
    state = track_b_state_from_plan(
        {
            "track_b_planned": True,
            "track_b_executed": False,
            "track_b_completed": False,
            "track_b_failed_honestly": False,
        }
    )
    assert state["track_b_planned"] is True
    assert state["track_b_executed"] is False
    body = compute_selection_verdict(
        stage_a_summary={"trials": 8},
        peak_contract=freeze_peak_contract(),
        champion=None,
        track_b_planned=True,
        track_b_executed=False,
        track_b_completed=False,
        track_b_failed_honestly=False,
        stage_b_trials=[{"ramp": {"passed": True}, "warning_gate": {"passed": False}}],
    )
    assert body["verdict"] == VERDICT_INCOMPLETE
    assert body["track_b_planned"] is True
    assert body["track_b_executed"] is False


def test_stage_b_status_labels_are_explicit():
    assert (
        classify_stage_b_status(eplus_ok=True, ramp_passed=True, warning_passed=False)
        == STATUS_RAMP_PASS_WARNING_FAIL
    )
    assert classify_stage_b_status(eplus_ok=True, ramp_passed=False, warning_passed=False) == "RAMP_FAIL"
    assert classify_stage_b_status(eplus_ok=False, ramp_passed=False, warning_passed=False) == "EPLUS_FAIL"
    assert classify_stage_b_status(eplus_ok=True, ramp_passed=True, warning_passed=True) == "DUAL_GATE_PASS"


def test_w2a_inventory_nine_units_and_hp_conflict():
    inv = json.loads((APP / "docs" / "audits" / "figures" / "a04v2" / "w2a_plant_inventory.json").read_text(encoding="utf-8"))
    assert inv["n_units"] == 9
    assert inv["hp_count_67_split_sum"] == 67
    assert inv["agg_v1_hp_sum"] == 79
    assert inv["n_heating_coil_objects"] == 9
    assert inv["identical_hardcoded_heating_w"] is True
    for u in inv["units"]:
        assert u["rated_heating_capacity_w"] == 149430.0
        assert u["rated_heating_cop"] == 4.5
        assert str(u["rated_htg_airflow"]).lower() == "autosize"


def test_peak_contract_frozen_not_dual_gate():
    peak = json.loads((APP / "docs" / "audits" / "figures" / "a04v2" / "peak_contract.json").read_text(encoding="utf-8"))
    assert peak["hard_gate_on_15min_vs_billed"] is False
    assert peak["legacy_250_290"]["enforced_in_a04v2_selection"] is False
    assert peak["utility_jan2026_billed_demand_kw"] == 284.82


def test_idf_objects_ignore_zonehvac_type_references():
    from eplus_gym.idf_objects import find_named_object, iter_objects

    src = (
        "ZoneHVAC:WaterToAirHeatPump,\n"
        "  Unit,\n"
        "  Coil:Heating:WaterToAirHeatPump:EquationFit,  !- Heating Coil Object Type\n"
        "  1F_Cafe_Kitchen WAHP Heating Coil;            !- Heating Coil Name\n"
        "Coil:Heating:WaterToAirHeatPump:EquationFit,\n"
        "  1F_Cafe_Kitchen WAHP Heating Coil,            !- Name\n"
        "  ,                                             !- Availability Schedule Name\n"
        "  Autosize,                                     !- Rated Air Flow Rate {m3/s}\n"
        "  149430;                                       !- Rated Heating Capacity {W}\n"
    )
    coils = iter_objects(src, "Coil:Heating:WaterToAirHeatPump:EquationFit")
    assert len(coils) == 1
    block = find_named_object(src, "Coil:Heating:WaterToAirHeatPump:EquationFit", "1F_Cafe_Kitchen WAHP Heating Coil")
    assert block is not None
    assert "149430" in block
    assert "ZoneHVAC" not in block


def test_builder_refuses_a04_overwrite():
    from a04v2_build_stage_b_candidate import build_child

    with pytest.raises(SystemExit, match="overwrite"):
        build_child(plant="a04_capacity", capmult=1.0, mass_m2=0.0, run_id="lakeside_w2a_a04_dual_champion.idf")


def test_hp_scaled_patches_all_nine_including_cafe():
    from a04v2_build_stage_b_candidate import HTG_TYPE, patch_hp_scaled
    from eplus_gym.idf_objects import field_by_comment, find_named_object, iter_objects

    src = (APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf").read_text(
        encoding="utf-8", errors="replace"
    )
    scaled = patch_hp_scaled(src)
    assert len(iter_objects(scaled, HTG_TYPE)) == 9
    cafe = find_named_object(scaled, HTG_TYPE, "1F_Cafe_Kitchen WAHP Heating Coil")
    assert cafe is not None
    cap = float(field_by_comment(cafe, "Rated Heating Capacity"))
    assert cap != 149430.0
    assert "149430" not in scaled


def test_sch_htgsp_replay_monday_and_sunday():
    from a04v2_compare_incumbent_schedules import SchHtgSpReplay

    # Monday 03:00 still setback; 03:15 occupied; 15:30 setback.
    assert SchHtgSpReplay.value_c(12, 0) == 7.78
    assert SchHtgSpReplay.value_c(13, 0) == 21.11
    assert SchHtgSpReplay.value_c(61, 0) == 21.11
    assert SchHtgSpReplay.value_c(62, 0) == 7.78
    assert SchHtgSpReplay.value_c(13, 5) == 7.78  # Saturday


def test_track_b_failed_honestly_is_terminal_nogo():
    body = compute_selection_verdict(
        stage_a_summary={"trials": 8},
        peak_contract=freeze_peak_contract(),
        champion=None,
        track_b_planned=True,
        track_b_executed=True,
        track_b_completed=False,
        track_b_failed_honestly=True,
        stage_b_trials=[{"ramp": {"passed": False}, "warning_gate": {"passed": False}}],
    )
    assert body["verdict"] == VERDICT_NOGO
    assert body["long_campaign_allowed"] is False
    body = compute_selection_verdict(
        stage_a_summary={"trials": 8},
        peak_contract=freeze_peak_contract(),
        champion=None,
        track_b_planned=True,
        track_b_executed=False,
        track_b_failed_honestly=False,
        stage_b_trials=[{"ramp": {"passed": False}, "warning_gate": {"passed": False}}],
    )
    assert body["verdict"] == VERDICT_INCOMPLETE
    assert body["long_campaign_allowed"] is False


def test_path_sanitize_strips_user_home():
    from eplus_gym.path_sanitize import redact_obj

    cleaned = redact_obj({"idf": r"C:\Users\ben\Documents\py-bacnet-stacks-playground\foo.idf"})
    assert "Users\\ben" not in cleaned["idf"]
    assert "<USER_HOME>" in cleaned["idf"]


def test_tracked_docs_have_no_machine_local_paths():
    banned = ("C:\\Users\\ben", "C:/Users/ben")
    roots = [
        APP / "AGENTS.md",
        APP / "config.example.py",
        APP / "docs" / "audits" / "2026-08-16-vibe22-a04v2-transient-nogo.md",
        APP / "docs" / "audits" / "2026-08-17-vibe22-a04v2-model-development-continues.md",
        APP / "data" / "DATA.md",
    ]
    hits = []
    for path in roots:
        text = path.read_text(encoding="utf-8")
        for ban in banned:
            if ban in text:
                hits.append(f"{path.name}:{ban}")
    assert hits == [], hits


def test_stage_b_child_regenerates_from_parent_and_manifest(tmp_path, monkeypatch):
    from a04v2_build_stage_b_candidate import build_child

    dest = APP / "models" / "eplus" / "a04v2_candidates" / "regen_smoke_closeout"
    try:
        monkeypatch.chdir(APP)
        meta = build_child(plant="autosize_htg", capmult=1.0, mass_m2=0.0, run_id="regen_smoke_closeout")
        idf = dest / meta["idf"]
        assert idf.is_file()
        text = idf.read_text(encoding="utf-8", errors="replace")
        assert "Autosize" in text
        assert meta["parent_model"] == "lakeside_w2a_a04_dual_champion.idf"
    finally:
        if dest.is_dir():
            for p in dest.iterdir():
                p.unlink()
            dest.rmdir()

