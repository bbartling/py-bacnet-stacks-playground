"""Fail-closed paired-comparison validation for Vibe22 scorecards."""
from __future__ import annotations

from typing import Any, Mapping


class PairedComparisonError(ValueError):
    pass


REQUIRED_KEYS = (
    "idf_sha256",
    "epw_sha256",
    "target_date",
    "baseline_contract_name",
    "baseline_contract_sha256",
    "action_contract_version",
    "heating_schedule_fingerprint",
    "energyplus_version",
)


def assert_pair_compatible(a: Mapping[str, Any], b: Mapping[str, Any], *, context: str = "") -> None:
    """Refuse cross-arm peak/cost deltas unless core provenance matches."""
    prefix = f"{context}: " if context else ""
    for key in (
        "idf_sha256",
        "epw_sha256",
        "target_date",
        "baseline_contract_name",
        "baseline_contract_sha256",
        "energyplus_version",
        "demand_interval",
        "lookback_dates",
        "tariff_mode",
        "opening_mtd_kw",
    ):
        if key not in a or key not in b:
            # Allow missing optional keys only if both missing
            if key in {"demand_interval", "lookback_dates", "tariff_mode", "opening_mtd_kw"}:
                if (key in a) != (key in b):
                    raise PairedComparisonError(f"{prefix}missing asymmetric key {key}")
                continue
            raise PairedComparisonError(f"{prefix}missing required key {key}")
        if a.get(key) != b.get(key):
            raise PairedComparisonError(
                f"{prefix}incompatible {key}: {a.get(key)!r} vs {b.get(key)!r}"
            )


def refuse_cross_experiment_peak_delta(
    *,
    peak_a: float,
    peak_b: float,
    meta_a: Mapping[str, Any],
    meta_b: Mapping[str, Any],
    claim: str,
) -> None:
    """Block 285→X style claims without same-day same-baseline evidence."""
    try:
        assert_pair_compatible(meta_a, meta_b, context=claim)
    except PairedComparisonError as exc:
        raise PairedComparisonError(
            f"Refusing peak delta claim {claim!r} ({peak_a} → {peak_b}): {exc}"
        ) from exc


def native_and_gym_must_not_share_contract_id(native_id: str, gym_id: str) -> None:
    if str(native_id) == str(gym_id):
        raise PairedComparisonError(
            "A04_NATIVE_CALIBRATION_REFERENCE and Gym/BAS baseline cannot share the same contract id"
        )


def demand_floor_must_be_explicit(opening_mtd_kw: float | None, *, allow_zero_with_disclosure: bool) -> None:
    if opening_mtd_kw is None:
        raise PairedComparisonError("opening_mtd_kw must be explicit (never silently omitted)")
    if float(opening_mtd_kw) == 0.0 and not allow_zero_with_disclosure:
        raise PairedComparisonError("opening_mtd_kw=0 requires explicit disclosure flag")
