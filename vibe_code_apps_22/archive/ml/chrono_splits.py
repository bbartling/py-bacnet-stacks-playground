"""Chronological (leakage-safe) split manifests for 15-min heating-DSM data.

Heating-day rule
----------------
A calendar ``day`` is treated as a *heating day* when **either** condition holds
over the rows of that day:

* ``mean(oat_f) <= 50.0`` (deg F), **or**
* the accumulated heating degree-hours base-65 reach the winter threshold. With
  15-minute rows we sum the per-row degree deficit ``max(0, 65 - oat_f)`` and
  scale by ``0.25`` h/step: ``sum(max(0, 65 - oat_f)) * 0.25 >= 12.0``. This is
  the 48.0 "HDD65 raw-sum" threshold expressed in degree-hours
  (``48 raw units * 0.25 h = 12 degree-hours``).

Manifest layout
---------------
``build_split_manifest`` returns a dict describing, in chronological order:

* ``all_days`` — every unique day.
* ``heating_days`` / ``non_heating_days`` — classification by the rule above.
* ``final_winter_test`` — the last ~15% of heating days that fall in months
  {12, 1, 2}; if there are too few such winter days we fall back to the last
  ``20`` heating days overall. This block is **never** used for model / champion
  selection — it is a single, held-until-the-end winter test.
* ``dev_days`` — heating days that remain for development (everything except the
  final winter test).
* ``folds`` — rolling-origin (expanding-train) cross-validation folds over
  ``dev_days``. Each fold's validation days are a contiguous chronological block
  near the tail; its training days are all development days strictly *before* the
  block (an expanding origin). A 1-day ``embargo`` gap is left between the train
  end and the validation start when there is room for it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HEATING_MEAN_OAT_F = 50.0
HEATING_DEGREE_HOURS = 12.0  # == 48.0 raw 15-min degree-deficit units * 0.25 h
FINAL_TEST_FRAC = 0.15
FINAL_TEST_FALLBACK_DAYS = 20
WINTER_MONTHS = (12, 1, 2)
N_FOLDS = 3
EMBARGO_DAYS = 1


def _day_order_key(day: Any) -> Any:
    """Return a sortable chronological key for a ``day`` label."""
    try:
        ts = pd.to_datetime(day)
        if pd.notna(ts):
            return (0, ts.to_pydatetime())
    except Exception:
        pass
    return (1, str(day))


def _sorted_unique_days(df: pd.DataFrame) -> list[Any]:
    days = list(pd.unique(df["day"]))
    return sorted(days, key=_day_order_key)


def _day_month(df_day: pd.DataFrame, day: Any) -> int:
    if "month" in df_day.columns and not df_day["month"].isna().all():
        return int(pd.to_numeric(df_day["month"], errors="coerce").dropna().iloc[0])
    try:
        return int(pd.to_datetime(day).month)
    except Exception:
        return 0


def is_heating_day(
    oat_f: np.ndarray,
    *,
    mean_oat_thresh: float = HEATING_MEAN_OAT_F,
    degree_hours_thresh: float = HEATING_DEGREE_HOURS,
) -> bool:
    """True when a day's outdoor-air-temp series qualifies as a heating day.

    See module docstring for the exact rule.
    """
    oat = np.asarray(oat_f, dtype=float)
    oat = oat[np.isfinite(oat)]
    if oat.size == 0:
        return False
    mean_oat = float(np.mean(oat))
    hdd_hours = float(np.sum(np.maximum(0.0, 65.0 - oat)) * 0.25)
    return (mean_oat <= mean_oat_thresh) or (hdd_hours >= degree_hours_thresh)


def _classify_days(df: pd.DataFrame, days: list[Any]) -> tuple[list, list, dict]:
    heating: list[Any] = []
    non_heating: list[Any] = []
    months: dict[Any, int] = {}
    grouped = {str(k): v for k, v in df.groupby("day")}
    for day in days:
        sub = grouped.get(str(day))
        if sub is None:
            sub = df[df["day"] == day]
        months[day] = _day_month(sub, day)
        oat = pd.to_numeric(sub.get("oat_f"), errors="coerce").to_numpy(dtype=float)
        if is_heating_day(oat):
            heating.append(day)
        else:
            non_heating.append(day)
    return heating, non_heating, months


def _pick_final_winter_test(
    heating_days: list[Any],
    months: dict[Any, int],
    *,
    frac: float = FINAL_TEST_FRAC,
    fallback_days: int = FINAL_TEST_FALLBACK_DAYS,
) -> list[Any]:
    """Final winter test block (never used for selection).

    When any {12,1,2} heating days exist, hold out the last ~``frac`` of them (at
    least one day). Only when there are **no** dedicated winter-month heating days
    do we fall back to the last ``fallback_days`` heating days overall. This keeps
    a non-empty development set even for short winter records.
    """
    if not heating_days:
        return []
    winter = [d for d in heating_days if months.get(d, 0) in WINTER_MONTHS]
    if winter:
        n_test = max(1, int(round(frac * len(winter))))
        return winter[-n_test:]
    # no dedicated winter-month heating days: hold out the last ``fallback_days``
    n_test = min(fallback_days, len(heating_days))
    if n_test <= 0:
        return []
    return heating_days[-n_test:]


def _rolling_origin_folds(
    dev_days: list[Any],
    *,
    n_folds: int = N_FOLDS,
    embargo: int = EMBARGO_DAYS,
) -> list[dict[str, list]]:
    """Expanding-train, contiguous-validation rolling-origin folds.

    Each validation block is a contiguous chronological chunk near the tail; the
    training set is every development day strictly before the block, minus an
    ``embargo`` gap when room allows. Folds that would yield an empty train or
    validation block are skipped.
    """
    n = len(dev_days)
    if n < 2:
        return []
    block = max(1, n // (n_folds + 1))
    folds: list[dict[str, list]] = []
    for k in range(n_folds):
        val_start = n - (n_folds - k) * block
        val_end = val_start + block
        if val_start <= 0 or val_start >= n:
            continue
        val = dev_days[val_start:val_end]
        train_end = val_start - embargo if (val_start - embargo) >= 1 else val_start
        embargo_days = dev_days[train_end:val_start]
        train = dev_days[:train_end]
        if not train or not val:
            continue
        folds.append(
            {
                "fold": k,
                "train": list(train),
                "val": list(val),
                "embargo": list(embargo_days),
            }
        )
    return folds


def build_split_manifest(
    df: pd.DataFrame,
    *,
    n_folds: int = N_FOLDS,
    embargo: int = EMBARGO_DAYS,
    final_test_frac: float = FINAL_TEST_FRAC,
) -> dict[str, Any]:
    """Build a leakage-safe chronological split manifest from a 15-min frame.

    Requires columns ``day`` and ``oat_f`` (``month`` is used when present, else
    inferred from the ``day`` label). See the module docstring for the rules.
    """
    if "day" not in df.columns:
        raise ValueError("build_split_manifest requires a 'day' column")
    if "oat_f" not in df.columns:
        raise ValueError("build_split_manifest requires an 'oat_f' column")

    all_days = _sorted_unique_days(df)
    heating_days, non_heating_days, months = _classify_days(df, all_days)
    final_test = _pick_final_winter_test(
        heating_days, months, frac=final_test_frac
    )
    final_set = {str(d) for d in final_test}
    dev_days = [d for d in heating_days if str(d) not in final_set]
    folds = _rolling_origin_folds(dev_days, n_folds=n_folds, embargo=embargo)

    def _as_str(seq: list[Any]) -> list[str]:
        return [str(x) for x in seq]

    return {
        "schema": "chrono_split_manifest_v1",
        "rule": {
            "heating_day": (
                "mean(oat_f)<=50.0 OR sum(max(0,65-oat_f))*0.25>=12.0 degree-hours"
            ),
            "final_winter_test": (
                "last ~15% of {12,1,2} heating days (never used for selection); "
                "fallback = last 20 heating days if too few winter days"
            ),
            "folds": (
                "rolling-origin expanding train; contiguous chronological "
                "validation blocks; 1-day embargo between train and val"
            ),
        },
        "params": {
            "heating_mean_oat_f": HEATING_MEAN_OAT_F,
            "heating_degree_hours": HEATING_DEGREE_HOURS,
            "final_test_frac": final_test_frac,
            "final_test_fallback_days": FINAL_TEST_FALLBACK_DAYS,
            "winter_months": list(WINTER_MONTHS),
            "n_folds": n_folds,
            "embargo_days": embargo,
        },
        "n_days_total": len(all_days),
        "n_heating_days": len(heating_days),
        "all_days": _as_str(all_days),
        "heating_days": _as_str(heating_days),
        "non_heating_days": _as_str(non_heating_days),
        "final_winter_test": _as_str(final_test),
        "dev_days": _as_str(dev_days),
        "folds": [
            {
                "fold": f["fold"],
                "train": _as_str(f["train"]),
                "val": _as_str(f["val"]),
                "embargo": _as_str(f["embargo"]),
            }
            for f in folds
        ],
    }


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> Path:
    """Write ``manifest`` as UTF-8 JSON and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path
