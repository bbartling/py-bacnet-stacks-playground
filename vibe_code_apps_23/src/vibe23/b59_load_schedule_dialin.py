"""Preregistered LOAD_SCHEDULE dial-in for Building 59 screening proxy.

Axes come from measured end-use over-prediction (MEL/lighting) and schedule
priors (weekend/standby fractions, occupancy hours, HVAC enable). Topology
blockers remain; claim status is never calibrated or DSM-ready.
"""

from __future__ import annotations

from dataclasses import replace

from .b59_campaign_runner import B59CampaignCandidate
from .b59_control_replay import CONTROL_REPLAY_BASE
from .b59_model import PUBLISHED_RTU_RATINGS, B59CalibrationParameters

CLAIM_STATUS = "LOAD_SCHEDULE_DIALIN_SCREENING_NOT_CALIBRATED"
MAX_LOAD_SCHEDULE_DIALIN_RUNS = 24

# CONTROL_REPLAY champion direction (R14 OA ×1.10) as the dial-in baseline.
LOAD_SCHEDULE_BASE = replace(
    CONTROL_REPLAY_BASE,
    minimum_outdoor_air_m3_s=1.10 * PUBLISHED_RTU_RATINGS.minimum_outdoor_air_m3_s,
)

# From config/b59_schedule_priors.json candidate scales (2018 weekday/weekend).
MEASURED_MEL_STANDBY = 0.40
MEASURED_MEL_WEEKEND = 0.65
MEASURED_LIGHTS_WEEKEND = 0.17
MEASURED_PEOPLE_WEEKEND = 0.04


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
        parent_run_id="control_replay_r14",
        holdout=False,
    )


def _with_measured_shapes(base: B59CalibrationParameters) -> B59CalibrationParameters:
    return replace(
        base,
        people_standby_fraction=0.0,
        people_weekend_fraction=MEASURED_PEOPLE_WEEKEND,
        lights_standby_fraction=0.05,
        lights_weekend_fraction=MEASURED_LIGHTS_WEEKEND,
        mel_standby_fraction=MEASURED_MEL_STANDBY,
        mel_weekend_fraction=MEASURED_MEL_WEEKEND,
    )


def load_schedule_dialin_candidates(
    base: B59CalibrationParameters = LOAD_SCHEDULE_BASE,
) -> tuple[B59CampaignCandidate, ...]:
    """Exactly 24 preregistered internal-load / schedule candidates."""
    shaped = _with_measured_shapes(base)
    items: list[B59CampaignCandidate] = []

    # R01 — control-replay R14-equivalent baseline (historical 0.05 load shapes).
    items.append(_cand(1, stage="baseline", families=("baseline",), parameters=base))

    # R02 — measured MEL/lights/people weekend+standby shapes only.
    items.append(
        _cand(2, stage="measured_shapes", families=("load_shape",), parameters=shaped)
    )

    # R03–R06 — MEL W/m2 ladder toward measured annual MEL (~28.5 MWh vs ~90 MWh sim).
    # Avoid 5.5 W/m2 + high lighting + high MEL standby: R05 warmup severes on
    # this PackagedVAV/UFAD proxy (loads init non-convergence).
    for ordinal, equip in enumerate((12.0, 8.0, 6.0, 4.0), start=3):
        items.append(
            _cand(
                ordinal,
                stage="mel_density",
                families=("equipment_w_m2", "load_shape"),
                parameters=replace(shaped, equipment_w_m2=equip),
            )
        )

    # R07–R10 — lighting W/m2 ladder toward measured lig_S (~6.4 MWh vs ~35 MWh sim).
    for ordinal, lights in enumerate((8.0, 5.0, 3.5, 2.5), start=7):
        items.append(
            _cand(
                ordinal,
                stage="lighting_density",
                families=("lighting_w_m2", "load_shape"),
                parameters=replace(shaped, lighting_w_m2=lights),
            )
        )

    # R11–R14 — joint MEL+lighting cuts with measured shapes.
    joint = (
        (8.0, 5.0),
        (5.5, 3.5),
        (4.5, 2.5),
        (4.0, 2.5),
    )
    for ordinal, (equip, lights) in enumerate(joint, start=11):
        items.append(
            _cand(
                ordinal,
                stage="joint_loads",
                families=("internal_loads", "load_shape"),
                parameters=replace(shaped, equipment_w_m2=equip, lighting_w_m2=lights),
            )
        )

    # R15–R16 — HVAC enable: continuous (baseline) vs weekday window on joint low loads.
    joint_low = replace(shaped, equipment_w_m2=5.5, lighting_w_m2=3.5)
    items.append(
        _cand(
            15,
            stage="hvac_enable",
            families=("hvac_availability", "internal_loads"),
            parameters=replace(joint_low, hvac_availability_mode="continuous"),
        )
    )
    items.append(
        _cand(
            16,
            stage="hvac_enable",
            families=("hvac_availability", "internal_loads"),
            parameters=replace(
                joint_low,
                hvac_availability_mode="weekday_window",
                weekday_hvac_start_hour=5.0,
                weekday_hvac_end_hour=22.0,
                weekday_occupancy_start_hour=7.0,
                weekday_occupancy_end_hour=18.0,
            ),
        )
    )

    # R17–R18 — occupancy timing from schedule priors on joint low + continuous HVAC.
    items.append(
        _cand(
            17,
            stage="occupancy_hours",
            families=("occupancy_hours", "internal_loads"),
            parameters=replace(
                joint_low,
                weekday_occupancy_start_hour=7.0,
                weekday_occupancy_end_hour=18.0,
                weekday_hvac_start_hour=5.0,
                weekday_hvac_end_hour=22.0,
            ),
        )
    )
    items.append(
        _cand(
            18,
            stage="occupancy_hours",
            families=("occupancy_hours", "internal_loads"),
            parameters=replace(
                joint_low,
                weekday_occupancy_start_hour=6.0,
                weekday_occupancy_end_hour=19.0,
                weekday_hvac_start_hour=4.5,
                weekday_hvac_end_hour=23.0,
            ),
        )
    )

    # R19 — fewer people (heat-gain only; camera is south-only).
    items.append(
        _cand(
            19,
            stage="people_density",
            families=("people_density", "internal_loads"),
            parameters=replace(joint_low, people_area_per_person_m2=30.0),
        )
    )

    # R20–R21 — post-March multipliers at evidence bounds on joint low.
    items.append(
        _cand(
            20,
            stage="pandemic_multipliers",
            families=("post_march_multipliers", "internal_loads"),
            parameters=replace(
                joint_low,
                post_march17_equipment_multiplier=0.15,
                post_march17_lighting_multiplier=0.20,
                post_march17_people_multiplier=0.10,
            ),
        )
    )
    items.append(
        _cand(
            21,
            stage="pandemic_multipliers",
            families=("post_march_multipliers", "internal_loads"),
            parameters=replace(
                joint_low,
                post_march17_equipment_multiplier=0.40,
                post_march17_lighting_multiplier=0.40,
                post_march17_people_multiplier=0.40,
            ),
        )
    )

    # R22–R24 — fan-power sensitivity (winter over-sim hypothesis) on joint low.
    for ordinal, pressure in enumerate((900.0, 750.0, 600.0), start=22):
        items.append(
            _cand(
                ordinal,
                stage="fan_pressure",
                families=("fan_pressure", "internal_loads"),
                parameters=replace(
                    joint_low,
                    supply_fan_pressure_pa=pressure,
                    return_fan_pressure_pa=max(200.0, pressure * 0.35),
                ),
            )
        )

    if len(items) != MAX_LOAD_SCHEDULE_DIALIN_RUNS:
        raise RuntimeError(f"expected {MAX_LOAD_SCHEDULE_DIALIN_RUNS} candidates; got {len(items)}")
    return tuple(items)
