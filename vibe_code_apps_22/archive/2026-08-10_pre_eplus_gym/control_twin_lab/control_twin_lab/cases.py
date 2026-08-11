"""Paired Control Twin Lab case matrix."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Strategy = Literal[
    "baseline",
    "stagger_preheat",
    "deep_setback",
    "flat_24_7",
    "prbs",
]

DESKTOP_SAFE = ("baseline", "stagger_preheat", "deep_setback", "flat_24_7")
SPINUPS = (0, 3, 7, 14)
TIMESTEPS = (4, 6, 12)


@dataclass(frozen=True)
class CaseSpec:
    eval_day: str
    strategy: str
    pre_roll_days: int
    steps_per_hour: int
    profile: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def farm_only_prbs(self) -> bool:
        return self.strategy == "prbs"


def smoke_cases(eval_day: str = "2026-01-26") -> list[CaseSpec]:
    """Tiny matrix for CI / laptop: 2 strategies × spin0 × ts6."""
    return [
        CaseSpec(eval_day, "baseline", 0, 6, "smoke"),
        CaseSpec(eval_day, "stagger_preheat", 0, 6, "smoke"),
    ]


def full_lab_cases(eval_day: str = "2026-01-26", *, include_prbs: bool = False) -> list[CaseSpec]:
    strategies = list(DESKTOP_SAFE) + (["prbs"] if include_prbs else [])
    out: list[CaseSpec] = []
    for pre in SPINUPS:
        for ts in TIMESTEPS:
            for strat in strategies:
                out.append(CaseSpec(eval_day, strat, pre, ts, "full_lab"))
    return out
