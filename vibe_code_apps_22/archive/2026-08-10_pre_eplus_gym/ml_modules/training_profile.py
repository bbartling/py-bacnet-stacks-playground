"""Immutable training / evaluation profiles (fail-closed; no silent smoke defaults)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

ProfileMode = Literal["smoke", "full_evaluation", "full_deployment"]

VALID_MODES: tuple[ProfileMode, ...] = ("smoke", "full_evaluation", "full_deployment")

ENV_PROFILE = "VIBE22_TRAINING_PROFILE"


@dataclass(frozen=True)
class TrainingProfile:
    """Shared profile for notebooks, export, and tests.

    Missing profile selection must fail closed — never silently pick smoke /
    ``MAX_DAYS=36``.
    """

    mode: ProfileMode
    max_days: int | None
    heating_only: bool = True
    require_complete_96_step_days: bool = True
    locked_test_fraction: float = 0.15
    minimum_development_days: int = 12
    minimum_locked_test_days: int = 3
    random_seeds: tuple[int, ...] = (0, 1, 2, 3, 4)
    watermark: str | None = None
    allow_desktop_library_export: bool = False
    allow_ml_desktop_promote_claims: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "max_days": self.max_days,
            "heating_only": self.heating_only,
            "require_complete_96_step_days": self.require_complete_96_step_days,
            "locked_test_fraction": self.locked_test_fraction,
            "minimum_development_days": self.minimum_development_days,
            "minimum_locked_test_days": self.minimum_locked_test_days,
            "random_seeds": list(self.random_seeds),
            "watermark": self.watermark,
            "allow_desktop_library_export": self.allow_desktop_library_export,
            "allow_ml_desktop_promote_claims": self.allow_ml_desktop_promote_claims,
        }

    @staticmethod
    def from_mode(mode: str) -> "TrainingProfile":
        m = str(mode).strip().lower()
        if m not in VALID_MODES:
            raise ValueError(
                f"unknown TrainingProfile mode={mode!r}; expected one of {VALID_MODES}"
            )
        if m == "smoke":
            return TrainingProfile(
                mode="smoke",
                max_days=36,
                watermark="SMOKE_ONLY",
                allow_desktop_library_export=False,
                allow_ml_desktop_promote_claims=False,
                random_seeds=(0,),
                minimum_development_days=6,
                minimum_locked_test_days=1,
            )
        if m == "full_evaluation":
            return TrainingProfile(
                mode="full_evaluation",
                max_days=None,
                watermark=None,
                allow_desktop_library_export=False,
                allow_ml_desktop_promote_claims=False,
            )
        # full_deployment
        return TrainingProfile(
            mode="full_deployment",
            max_days=None,
            watermark="DEPLOYMENT_REFIT",
            allow_desktop_library_export=True,
            allow_ml_desktop_promote_claims=True,
        )


def require_profile(
    mode: str | None = None,
    *,
    env: bool = True,
    env_var: str = ENV_PROFILE,
) -> TrainingProfile:
    """Resolve profile from explicit mode or env; raise if neither is set."""
    chosen = mode
    if chosen is None and env:
        chosen = os.environ.get(env_var)
    if chosen is None or str(chosen).strip() == "":
        raise ValueError(
            f"TrainingProfile required: pass mode=... or set {env_var} to one of {VALID_MODES}. "
            "Silent MAX_DAYS=36 / smoke defaults are not allowed."
        )
    return TrainingProfile.from_mode(str(chosen))


def assert_desktop_library_allowed(profile: TrainingProfile) -> None:
    if not profile.allow_desktop_library_export:
        raise PermissionError(
            f"desktop nearest-day library export refused for profile mode={profile.mode!r} "
            f"(watermark={profile.watermark!r}); require full_deployment"
        )


def profile_day_summary(
    *,
    source_days: Sequence[Any],
    complete_days: Sequence[Any],
    heating_days: Sequence[Any],
    development_days: Sequence[Any],
    locked_test_days: Sequence[Any],
    folds: Sequence[dict[str, Any]] | None = None,
    deployment_refit_days: Sequence[Any] | None = None,
    profile: TrainingProfile,
) -> dict[str, Any]:
    """Counts / spans for notebook printing."""

    def _span(days: Sequence[Any]) -> dict[str, str | None]:
        if not days:
            return {"earliest": None, "latest": None}
        s = sorted(str(d) for d in days)
        return {"earliest": s[0], "latest": s[-1]}

    fold_rows = []
    for f in folds or []:
        fold_rows.append(
            {
                "fold": f.get("fold"),
                "n_train": len(f.get("train") or []),
                "n_val": len(f.get("val") or []),
                "n_embargo": len(f.get("embargo") or []),
            }
        )
    return {
        "profile": profile.to_dict(),
        "n_source_days": len(source_days),
        "n_complete_days": len(complete_days),
        "n_heating_eligible_days": len(heating_days),
        "n_development_days": len(development_days),
        "n_locked_test_days": len(locked_test_days),
        "n_deployment_refit_days": len(deployment_refit_days or []),
        "folds": fold_rows,
        "span_complete": _span(complete_days),
        "span_heating": _span(heating_days),
    }
