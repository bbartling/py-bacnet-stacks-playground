"""Final physics-repair + research-PoC gates. No EnergyPlus in this module."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from eplus_gym.a04_identity import (
    A04_GIT_BLOB,
    A04_IDF_NAME,
    A04_SHA_CRLF,
    A04_SHA_LF,
    is_allowed_lakeside_gym_idf,
    is_trackc_idf_filename,
)
from eplus_gym.a04_manifest import load_a04_model_manifest, verify_a04_bytes
from eplus_gym.control_v2 import ACTION_KEYS, build_six_schedules_f, continuous_params, school_windows
from eplus_gym.date_use_ledger import NO_LOCKED_UNSEEN, classify_date_use, locked_unseen_available
from eplus_gym.eplus_output_discovery import parse_rdd_variable_names, select_confirmed_variables
from eplus_gym.idf_diagnostics import (
    aggregate_heating_capacity_w,
    count_w2a_objects,
    strip_invalid_ideal_loads_and_district,
)
from eplus_gym.rl.active_model import ActiveModelError, load_active_model
from eplus_gym.rl.billing_state import BillingState
from eplus_gym.rl.multiday_env import FakeContinuityPlant, assert_live_campaign_plant
from eplus_gym.rl.operator_pay_experiment import refuse_full_campaign
from eplus_gym.rl.research_model import ResearchModelError, load_research_model, verify_research_model
from eplus_gym.rl.research_spaces import (
    RESEARCH_UNOCC_F_LO,
    decode_continuous_research,
    decode_discrete_research,
    discrete_n_research,
    frozen_school_occupancy,
    research_continuous_68,
    research_continuous_70,
)
from eplus_gym.rl.reward_v2 import utility_accounting
from eplus_gym.rl.sb3_configs import named_config
from eplus_gym.rl.split_manifest import TRAIN_END, build_split_manifest
from eplus_gym.trackc_one_w2a import (
    C2_HEATING_W,
    TRACK_C3_SKIP_REASON,
    allocate_heating_by_inventory,
    one_w2a_per_zone_ok,
    trackc3_allowed,
)
from eplus_gym.trajectory_guards import TrajectoryGuardError, validate_96_row_facility
from eplus_gym.w2a_invalid_domain import ACTIVE_AIRFLOW_FRACTION, classify_coil_timestep, count_active_invalid

APP = Path(__file__).resolve().parents[1]
A04 = APP / "models" / "eplus" / A04_IDF_NAME
TRACK_B_RESEARCH = APP / "models" / "eplus" / "research" / "a04_trackb_40fb33e8_NOT_CHAMPION.idf"
TRACK_B_SHA = "40fb33e863e5d04cabf087be42b74cc38de67d5030a2534e54847a98aa54029a"


def test_a04_raw_and_lf_hashes_and_git_blob():
    raw = A04.read_bytes()
    working = hashlib.sha256(raw).hexdigest()
    assert working in {A04_SHA_CRLF, A04_SHA_LF}
    lf = hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
    assert lf == A04_SHA_LF
    blob = subprocess.check_output(["git", "hash-object", str(A04)], text=True).strip()
    assert blob == A04_GIT_BLOB
    verify_a04_bytes(raw)
    man = load_a04_model_manifest(APP)
    assert man["sha256_crlf"] == A04_SHA_CRLF
    assert man["sha256_lf"] == A04_SHA_LF
    assert man["git_blob"] == A04_GIT_BLOB
    assert man["monthly_gl14_does_not_validate_15min_dsm"] is True


def test_a04_bytes_immutable_line_endings():
    raw = A04.read_bytes()
    lf = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    assert hashlib.sha256(lf).hexdigest() == A04_SHA_LF
    assert hashlib.sha256(crlf).hexdigest() == A04_SHA_CRLF
    assert A04_SHA_CRLF != A04_SHA_LF


def test_trackb_research_child_hash_and_labels():
    # Filename embeds the LF digest; Windows checkouts may present CRLF bytes.
    raw = TRACK_B_RESEARCH.read_bytes()
    lf = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    digest = hashlib.sha256(lf).hexdigest()
    assert digest == TRACK_B_SHA
    card = json.loads(
        (APP / "models" / "eplus" / "research" / "a04_trackb_40fb33e8_model_card.json").read_text(
            encoding="utf-8"
        )
    )
    for token in ("NOT_CHAMPION", "SIMULATION_ONLY", "TRANSIENT_NOT_VALIDATED", "W2A_WARNING_GATE_FAILED"):
        blob = json.dumps(card)
        assert token in blob
    assert card["champion"] is False
    assert "best" not in json.dumps(card).lower()
    assert "validated" not in json.dumps(card).lower() or "NOT_VALIDATED" in json.dumps(card)


def test_energyplus_object_counts_and_capacity():
    a04 = A04.read_text(encoding="utf-8", errors="replace")
    tb = TRACK_B_RESEARCH.read_text(encoding="utf-8", errors="replace")
    a04_c = count_w2a_objects(a04)
    tb_c = count_w2a_objects(tb)
    assert a04_c["n_heating_coils"] == 9
    assert a04_c["n_zonehvac"] == 9
    assert a04_c["n_equipment_lists"] == 9
    assert tb_c["n_heating_coils"] == 20
    assert tb_c["n_zonehvac"] == 20
    assert aggregate_heating_capacity_w(a04) == pytest.approx(1_344_870.0)
    assert one_w2a_per_zone_ok(a04) is True
    assert one_w2a_per_zone_ok(tb) is False


def test_rdd_discovery_and_confirmed_names():
    rdd = (
        "Output:Variable,*,Heating Coil Air Mass Flow Rate,hourly; !- HVAC Average [kg/s]\n"
        "Output:Variable,*,Heating Coil Runtime Fraction,hourly; !- HVAC Average []\n"
        "Output:Variable,*,Fan Air Mass Flow Rate,hourly; !- HVAC Average [kg/s]\n"
        "Output:Variable,*,Bogus Invented Meter,hourly; !- HVAC Average [W]\n"
    )
    names = parse_rdd_variable_names(rdd)
    assert "Heating Coil Air Mass Flow Rate" in names
    confirmed = select_confirmed_variables(
        names,
        [
            "Heating Coil Air Mass Flow Rate",
            "Heating Coil Runtime Fraction",
            "Heating Coil Invented Name",
        ],
    )
    assert confirmed == ["Heating Coil Air Mass Flow Rate", "Heating Coil Runtime Fraction"]
    assert "Heating Coil Invented Name" not in confirmed


def test_w2a_active_invalid_domain_classifier():
    bad = classify_coil_timestep(runtime_fraction=0.5, actual_air_kg_s=0.1, rated_air_kg_s=1.0)
    assert bad["invalid_domain"] is True
    assert bad["airflow_fraction"] == pytest.approx(0.1)
    ok = classify_coil_timestep(runtime_fraction=0.5, actual_air_kg_s=0.5, rated_air_kg_s=1.0)
    assert ok["invalid_domain"] is False
    idle = classify_coil_timestep(runtime_fraction=0.0, actual_air_kg_s=0.0, rated_air_kg_s=1.0)
    assert idle["invalid_domain"] is False
    rows = [bad, ok, idle]
    assert count_active_invalid(rows) == 1
    assert ACTIVE_AIRFLOW_FRACTION == 0.25


def test_96_row_nan_and_kw_plausibility():
    good = [10.0] * 96
    validate_96_row_facility(good)
    with pytest.raises(TrajectoryGuardError, match="96"):
        validate_96_row_facility([10.0] * 95)
    with pytest.raises(TrajectoryGuardError, match="NaN"):
        validate_96_row_facility([float("nan")] + [10.0] * 95)
    with pytest.raises(TrajectoryGuardError, match="Inf"):
        validate_96_row_facility([float("inf")] + [10.0] * 95)
    with pytest.raises(TrajectoryGuardError, match="negative"):
        validate_96_row_facility([-1.0] + [10.0] * 95)
    with pytest.raises(TrajectoryGuardError, match="400"):
        validate_96_row_facility([401.0] + [10.0] * 95)


def test_fixed_school_occupancy_and_continuous_and_gradual_ramp():
    win = school_windows("2026-01-12")
    occ = frozen_school_occupancy("2026-01-12")
    assert occ["heating_setpoint_start_step"] == win["school_occupied_start_step"]
    p = decode_continuous_research([70.0, 66.0, 60.0, 0, 0, 0, 0, 0, 0], day="2026-01-12")
    assert p.heating_setpoint_start_step == occ["heating_setpoint_start_step"]
    assert p.heating_setpoint_end_step == occ["heating_setpoint_end_step"]
    assert p.unoccupied_heating_f >= RESEARCH_UNOCC_F_LO
    series = build_six_schedules_f(p)
    assert set(series) == set(ACTION_KEYS)
    start = p.heating_setpoint_start_step
    steps = series["1F_A"]
    deltas = [abs(steps[i] - steps[i - 1]) for i in range(1, start + 1)]
    assert max(deltas) <= 2.651 + 1e-6
    c68 = research_continuous_68()
    c70 = research_continuous_70()
    assert c68.continuous_conditioning and c70.continuous_conditioning
    s70 = build_six_schedules_f(c70)["1F_A"]
    assert s70 == [70.0] * 96
    assert c68.occupied_heating_f == 68.0
    assert abs(c68.occupied_heating_f - 68.0) < 1e-9


def test_six_control_groups_present():
    p = decode_discrete_research(0, day="2026-01-12")
    sched = build_six_schedules_f(p)
    assert len(sched) == 6
    assert set(sched) == set(ACTION_KEYS)


def test_research_excludes_deep_setback():
    assert RESEARCH_UNOCC_F_LO >= 66.0
    for i in range(discrete_n_research()):
        p = decode_discrete_research(i, day="2026-01-12")
        assert p.unoccupied_heating_f >= RESEARCH_UNOCC_F_LO


def test_no_candidate_as_baseline_and_one_process_guard():
    with pytest.raises(ValueError, match="FakeContinuityPlant"):
        assert_live_campaign_plant(FakeContinuityPlant())
    from eplus_gym.rl.research_poc import refuse_fake_plant, reject_candidate_as_baseline

    with pytest.raises(ValueError, match="FakeContinuityPlant"):
        refuse_fake_plant(FakeContinuityPlant())
    with pytest.raises(ValueError, match="candidate-as-baseline"):
        reject_candidate_as_baseline({"sha": "aaa"}, {"sha": "aaa"})
    reject_candidate_as_baseline({"sha": "aaa"}, {"sha": "bbb"})


def test_reward_v2_mtd_demand_floor_carryover():
    billing = BillingState()
    d1 = utility_accounting([100.0] * 96, mtd_peak_kw=billing.start_of_day("2025-12-08"))
    billing.observe_peak(d1["day_peak_kw"])
    d2 = utility_accounting([80.0] * 96, mtd_peak_kw=billing.start_of_day("2025-12-09"))
    assert d2["old_floor_kw"] == pytest.approx(100.0)
    assert d2["demand_increment"] == pytest.approx(0.0)
    d3 = utility_accounting([120.0] * 96, mtd_peak_kw=billing.start_of_day("2025-12-10"))
    assert d3["demand_increment"] == pytest.approx(15.0 * 20.0)


def test_research_mode_cannot_enable_full_and_full_stays_exit_4():
    body = load_active_model(APP)
    assert body["long_campaign_allowed"] is False
    research = load_research_model(APP)
    assert research["research_poc_allowed"] is True
    assert research["simulation_training_ready"] is False
    assert research["operational_dsm_ready"] is False
    assert research["long_campaign_allowed"] is False
    verify_research_model(APP)
    with pytest.raises(ResearchModelError, match="long_campaign_allowed"):
        verify_research_model(
            APP,
            override={**research, "long_campaign_allowed": True},
        )
    decision = refuse_full_campaign(APP)
    assert decision["allowed"] is False
    import sys

    sys.path.insert(0, str(APP / "scripts"))
    import vibe22_rl

    rc = vibe22_rl.main(["campaign", "--simulator", "LIVE_ENERGYPLUS", "--n-days", "3"])
    assert rc == vibe22_rl.EXIT_INTEGRITY
    rc_missing = vibe22_rl.main(["research-poc", "--max-wall-hours", "6"])
    assert rc_missing == vibe22_rl.EXIT_INTEGRITY


def test_research_poc_named_config_is_not_full_or_long():
    cfg = named_config("research_poc")
    assert cfg["name"] == "research_poc"
    assert cfg["timesteps"] < named_config("long_poc")["ppo"]["n_steps"]
    with pytest.raises(ValueError):
        named_config("full")


def test_date_use_holdout_leakage_january_is_development():
    assert classify_date_use("2026-01-12", physics_inspected={"2026-01-12"}) == "development_evidence_not_holdout"
    assert locked_unseen_available({"2026-01-12"}) is False
    assert NO_LOCKED_UNSEEN in "NO LOCKED UNSEEN TEST AVAILABLE"
    man = build_split_manifest(["2025-12-08", "2025-12-20", "2026-01-12"])
    assert "2025-12-08" in man["train"]
    assert "2025-12-20" in man["validation"]
    assert "2026-01-12" in man["locked_test"]
    assert TRAIN_END.isoformat() == "2025-12-14"


def test_deterministic_resume_checkpoint_schema():
    from eplus_gym.rl.research_poc import checkpoint_complete, new_checkpoint

    ckpt = new_checkpoint(seed=7, valid_transition_count=3, idf_sha256="aa", epw_sha256="bb")
    assert checkpoint_complete(ckpt) is True
    ckpt2 = new_checkpoint(seed=7, valid_transition_count=3, idf_sha256="aa", epw_sha256="bb")
    assert ckpt["rng"] == ckpt2["rng"]
    incomplete = dict(ckpt)
    del incomplete["valid_transition_count"]
    assert checkpoint_complete(incomplete) is False


def test_strip_ideal_loads_and_district_when_absent():
    src = (
        "Output:Variable,*,Zone Ideal Loads Supply Air Sensible Heating Energy,Timestep;\n"
        "Output:Meter,DistrictHeatingWater:Facility,Timestep;\n"
        "Output:Meter,Electricity:Facility,Timestep;\n"
        "Output:Variable,*,Zone Mean Air Temperature,Timestep;\n"
    )
    out = strip_invalid_ideal_loads_and_district(src, has_ideal_loads=False, has_district=False)
    assert "Ideal Loads" not in out
    assert "DistrictHeating" not in out
    assert "Electricity:Facility" in out
    assert "Zone Mean Air Temperature" in out


def test_trackc_allocation_and_c3_skip():
    alloc = allocate_heating_by_inventory(800_000.0)
    assert abs(sum(alloc.values()) - 800_000.0) < 1e-6
    assert alloc["1F_Area_A"] > alloc["1F_Library_IMC"]
    assert 675_000 <= C2_HEATING_W["base"] <= 940_000
    assert trackc3_allowed(valid_speed_points=0) is False
    assert "unverified" in TRACK_C3_SKIP_REASON.lower() or "valid" in TRACK_C3_SKIP_REASON.lower()


def test_gym_allowlist_includes_trackc_not_not_champion_as_champion():
    assert is_trackc_idf_filename("lakeside_w2a_trackc_c1_child.idf")
    assert is_allowed_lakeside_gym_idf("lakeside_w2a_trackc_c1_child.idf")
    assert not is_allowed_lakeside_gym_idf("a04_trackb_40fb33e8_NOT_CHAMPION.idf")


def test_sanitized_evidence_has_no_client_identity():
    path = APP / "docs" / "audits" / "figures" / "vibe22_final_physics_rl" / "sanitized_evidence_matrix.json"
    text = path.read_text(encoding="utf-8").lower()
    for needle in ("phone", "@", "street", "avenue", "wisconsin department"):
        assert needle not in text
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["high_confidence"]["floor_area_ft2_target"] == 91210
    assert body["project_bas"]["heat_pump_records"] == 67
    assert body["project_bas"]["identical_physical_units_proven"] is False
