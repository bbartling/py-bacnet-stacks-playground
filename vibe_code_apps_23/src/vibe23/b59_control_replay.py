"""Preregistered 30-run CONTROL_REPLAY screening for Building 59.

Axes come from the measured-vs-IDF discrepancy audit (SAT SP, zone setpoints,
OA minimum, cooling capacity + coil airflow). Topology blockers remain; this
campaign must never be labeled calibrated or DSM-ready.
"""

from __future__ import annotations

from dataclasses import replace

from .b59_campaign_runner import B59CampaignCandidate
from .b59_model import CFM_TO_M3_S, PUBLISHED_RTU_RATINGS, B59CalibrationParameters

CLAIM_STATUS = "CONTROL_REPLAY_SCREENING_NOT_CALIBRATED"
MAX_CONTROL_REPLAY_RUNS = 30

# Champion screening parameters (historical R49 lineage), plus explicit SAT.
CONTROL_REPLAY_BASE = B59CalibrationParameters(
    people_area_per_person_m2=20.0,
    lighting_w_m2=11.0,
    equipment_w_m2=15.0,
    wall_thermal_resistance_m2_k_w=2.5,
    roof_thermal_resistance_m2_k_w=5.3,
    glazing_u_w_m2_k=2.0,
    glazing_shgc=0.35,
    infiltration_m3_s_m2=0.0003,
    measured_south_lighting_fraction=0.5,
    weekday_occupancy_start_hour=8.0,
    weekday_occupancy_end_hour=18.0,
    weekday_hvac_start_hour=4.5,
    weekday_hvac_end_hour=23.0,
    hvac_availability_mode="continuous",
    occupancy_calendar_mode="pandemic_2020",
    post_march17_people_multiplier=0.25,
    post_march17_lighting_multiplier=0.27392578125,
    post_march17_equipment_multiplier=0.2437596642368014,
    occupied_heating_setpoint_c=21.8,
    occupied_cooling_setpoint_c=23.2,
    unoccupied_heating_setpoint_c=15.6,
    unoccupied_cooling_setpoint_c=29.4,
    supply_fan_pressure_pa=1100.0,
    supply_fan_total_efficiency=0.7,
    return_fan_pressure_pa=415.0,
    return_fan_total_efficiency=0.7,
    cooling_cop=4.1,
    cooling_capacity_w=142432.54002,
    cooling_shr=0.7,
    coil_airflow_m3_s=13_500.0 * CFM_TO_M3_S,
    minimum_outdoor_air_m3_s=PUBLISHED_RTU_RATINGS.minimum_outdoor_air_m3_s,
    supply_air_temperature_setpoint_c=14.4,
)


def _cand(
    ordinal: int,
    *,
    stage: str,
    families: tuple[str, ...],
    parameters: B59CalibrationParameters,
) -> B59CampaignCandidate:
    return B59CampaignCandidate(
        ordinal=ordinal,
        run_id=f"R{ordinal:02d}",
        stage=stage,
        parameter_families=families,
        parameters=parameters,
        parent_run_id="champion_screening",
        holdout=False,
    )


def control_replay_candidates(
    base: B59CalibrationParameters = CONTROL_REPLAY_BASE,
) -> tuple[B59CampaignCandidate, ...]:
    """Exactly 30 preregistered control/rating candidates.

    Families are limited to discrepancy axes. Published 20,000 cfm remains
    outside the TwoSpeedDX rated domain; airflow stays inside the proxy coil
    envelope while capacity moves toward the published 30-ton rating.
    """
    published_cap = PUBLISHED_RTU_RATINGS.cooling_capacity_w
    items: list[B59CampaignCandidate] = []

    # R01 — frozen champion control baseline (SAT still 14.4 C).
    items.append(_cand(1, stage="baseline", families=("baseline",), parameters=base))

    # R02–R06 — SAT ladder toward measured medians, keeping zone-cool − SAT ≥ 5.5 C
    # so PackagedVAV sizing does not emit UpdateZoneSizing warnings on this proxy.
    sat_ladder = (
        (16.0, 23.2),
        (17.5, 23.2),
        (18.5, 24.5),
        (19.0, 25.0),
        (19.5, 25.5),
    )
    for ordinal, (sat_c, cool_c) in enumerate(sat_ladder, start=2):
        items.append(
            _cand(
                ordinal,
                stage="sat_ladder",
                families=("sat_setpoint", "setpoints"),
                parameters=replace(
                    base,
                    supply_air_temperature_setpoint_c=sat_c,
                    occupied_cooling_setpoint_c=cool_c,
                ),
            )
        )

    # R07–R10 — zone setpoint pairs around measured diversity center.
    zone_pairs = (
        (21.0, 24.0),
        (21.8, 23.2),  # champion / measured-ish center
        (20.5, 23.5),
        (21.5, 24.5),
    )
    for ordinal, (heat_c, cool_c) in enumerate(zone_pairs, start=7):
        items.append(
            _cand(
                ordinal,
                stage="zone_setpoints",
                families=("setpoints",),
                parameters=replace(
                    base,
                    occupied_heating_setpoint_c=heat_c,
                    occupied_cooling_setpoint_c=cool_c,
                ),
            )
        )

    # R11–R14 — outdoor-air minimum scale (published OA is already the base).
    for ordinal, scale in enumerate((0.85, 0.95, 1.05, 1.10), start=11):
        items.append(
            _cand(
                ordinal,
                stage="outdoor_air",
                families=("outdoor_air",),
                parameters=replace(
                    base,
                    minimum_outdoor_air_m3_s=scale * PUBLISHED_RTU_RATINGS.minimum_outdoor_air_m3_s,
                ),
            )
        )

    # R15–R20 — capacity/airflow toward published rating (DX-domain coupled).
    cooling_rows = (
        (1.35 * published_cap, 13_500.0 * CFM_TO_M3_S),  # near champion
        (1.20 * published_cap, 12_500.0 * CFM_TO_M3_S),
        (1.10 * published_cap, 12_000.0 * CFM_TO_M3_S),
        (1.00 * published_cap, 12_000.0 * CFM_TO_M3_S),  # published tons + proxy cfm
        (0.95 * published_cap, 11_500.0 * CFM_TO_M3_S),
        (1.00 * published_cap, 11_000.0 * CFM_TO_M3_S),
    )
    for ordinal, (cap_w, airflow) in enumerate(cooling_rows, start=15):
        items.append(
            _cand(
                ordinal,
                stage="cooling_rating",
                families=("cooling",),
                parameters=replace(
                    base,
                    cooling_capacity_w=cap_w,
                    coil_airflow_m3_s=airflow,
                ),
            )
        )

    # R21–R26 — SAT + OA combinations (two families max); keep zone-cool − SAT ≥ 5.5 C.
    combo_sat_oa = (
        (17.5, 23.2, 1.00),
        (17.5, 23.2, 1.10),
        (18.5, 24.5, 1.00),
        (18.5, 24.5, 1.10),
        (19.0, 25.0, 1.05),
        (16.0, 23.2, 1.10),
    )
    for ordinal, (sat_c, cool_c, oa_scale) in enumerate(combo_sat_oa, start=21):
        items.append(
            _cand(
                ordinal,
                stage="sat_oa",
                families=("sat_setpoint", "outdoor_air"),
                parameters=replace(
                    base,
                    supply_air_temperature_setpoint_c=sat_c,
                    occupied_cooling_setpoint_c=cool_c,
                    minimum_outdoor_air_m3_s=oa_scale * PUBLISHED_RTU_RATINGS.minimum_outdoor_air_m3_s,
                ),
            )
        )

    # R27–R30 — SAT + cooling rating combinations.
    combo_sat_cool = (
        (17.5, 23.2, 1.00 * published_cap, 12_000.0 * CFM_TO_M3_S),
        (18.5, 24.5, 1.00 * published_cap, 12_000.0 * CFM_TO_M3_S),
        (17.5, 23.2, 1.10 * published_cap, 12_500.0 * CFM_TO_M3_S),
        (18.5, 24.5, 0.95 * published_cap, 11_500.0 * CFM_TO_M3_S),
    )
    for ordinal, (sat_c, cool_c, cap_w, airflow) in enumerate(combo_sat_cool, start=27):
        items.append(
            _cand(
                ordinal,
                stage="sat_cooling",
                families=("sat_setpoint", "cooling"),
                parameters=replace(
                    base,
                    supply_air_temperature_setpoint_c=sat_c,
                    occupied_cooling_setpoint_c=cool_c,
                    cooling_capacity_w=cap_w,
                    coil_airflow_m3_s=airflow,
                ),
            )
        )

    if len(items) != MAX_CONTROL_REPLAY_RUNS:
        raise RuntimeError(f"expected {MAX_CONTROL_REPLAY_RUNS} candidates; got {len(items)}")
    return tuple(items)
