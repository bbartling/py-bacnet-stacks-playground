"""Hard sanity gates for hybrid DSM walks — reject impossible plant kW."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Lakeside meter peak ~300 kW; hard reject above this screening cap.
PLANT_PEAK_CAP_KW = 450.0
HYBRID_KW_FLOOR = 0.0
# IdealLoads delta smoke can be large; reject walks that exceed this |Δ| peak.
DELTA_ABS_CAP_KW = 350.0

REJECTED_SPIKE_OUTCOME = "REJECTED_HYBRID_SPIKE"
OK_OUTCOME = "OK"


@dataclass(frozen=True)
class RejectReason:
    code: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


def walk_kw_series(walk: dict[str, Any], key: str = "hybrid_facility_kw") -> list[float]:
    steps = walk.get("steps") or []
    return [float(s[key]) for s in steps if key in s]


def assert_walk_sane(
    walk: dict[str, Any],
    *,
    plant_cap_kw: float = PLANT_PEAK_CAP_KW,
    kw_floor: float = HYBRID_KW_FLOOR,
    delta_abs_cap_kw: float = DELTA_ABS_CAP_KW,
) -> RejectReason | None:
    """Return a RejectReason if the walk is physically implausible; else None."""
    hybrid = walk_kw_series(walk, "hybrid_facility_kw")
    if not hybrid:
        return RejectReason("empty_walk", "walk has no hybrid_facility_kw steps")
    h_min, h_max = float(min(hybrid)), float(max(hybrid))
    if h_max > plant_cap_kw:
        return RejectReason(
            "hybrid_above_plant_cap",
            f"max hybrid_facility_kw={h_max:.1f} > PLANT_PEAK_CAP_KW={plant_cap_kw:g}",
        )
    if h_min < kw_floor:
        return RejectReason(
            "hybrid_below_floor",
            f"min hybrid_facility_kw={h_min:.1f} < HYBRID_KW_FLOOR={kw_floor:g}",
        )
    deltas = walk_kw_series(walk, "delta_facility_kw")
    if deltas:
        d_abs = max(abs(float(x)) for x in deltas)
        if d_abs > delta_abs_cap_kw:
            return RejectReason(
                "delta_abs_above_cap",
                f"max |delta_facility_kw|={d_abs:.1f} > DELTA_ABS_CAP_KW={delta_abs_cap_kw:g}",
            )
    return None


def annotate_walk_sanity(walk: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Mutate walk summary with sanity fields; return the walk."""
    reason = assert_walk_sane(walk, **kwargs)
    hybrid = walk_kw_series(walk, "hybrid_facility_kw")
    deltas = walk_kw_series(walk, "delta_facility_kw")
    summary = walk.setdefault("summary", {})
    if hybrid:
        summary["min_kw_hybrid"] = float(min(hybrid))
        summary["max_kw_hybrid"] = float(max(hybrid))
    if deltas:
        summary["max_abs_delta_kw"] = float(max(abs(float(x)) for x in deltas))
    summary["plant_peak_cap_kw"] = float(kwargs.get("plant_cap_kw", PLANT_PEAK_CAP_KW))
    if reason is None:
        summary["outcome_flag"] = summary.get("outcome_flag") or OK_OUTCOME
        summary["reject_reasons"] = []
        summary["sane"] = True
    else:
        summary["outcome_flag"] = REJECTED_SPIKE_OUTCOME
        summary["reject_reasons"] = [reason.as_dict()]
        summary["sane"] = False
    walk["sane"] = summary["sane"]
    return walk


def card_reports_spike_risk(
    card: dict[str, Any],
    *,
    plant_cap_kw: float = PLANT_PEAK_CAP_KW,
) -> RejectReason | None:
    """Reject promote when recursive card already shows impossible peak-mag error."""
    rec = card.get("cv_recursive_96_heldout") or {}
    champ = card.get("champion")
    block = rec.get(champ) if isinstance(rec, dict) and champ in rec else rec
    if not isinstance(block, dict):
        return None
    # daily_peak_mag_error_kw ≈ |pred_peak − actual_peak|; huge values ⇒ spike risk
    for key in ("daily_peak_mag_error_kw", "facility_kw_mae_peak_05_09", "mae_delta_kw_peak"):
        val = block.get(key)
        if val is None:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        if key == "daily_peak_mag_error_kw" and v > plant_cap_kw:
            return RejectReason(
                "card_peak_mag_error",
                f"{key}={v:.1f} > plant_cap={plant_cap_kw:g}",
            )
    max_abs = block.get("max_abs_delta_kw_heldout") or card.get("max_abs_delta_kw_heldout")
    if max_abs is not None:
        try:
            if float(max_abs) > DELTA_ABS_CAP_KW:
                return RejectReason(
                    "card_max_abs_delta",
                    f"max_abs_delta_kw_heldout={float(max_abs):.1f} > {DELTA_ABS_CAP_KW:g}",
                )
        except (TypeError, ValueError):
            pass
    return None
