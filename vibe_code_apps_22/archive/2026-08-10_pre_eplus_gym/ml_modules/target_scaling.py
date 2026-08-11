"""Per-target standardization for multi-output DSM (facility_kw + 6 zone temps).

Fit on training rows only. Never fit on validation / locked-test rows.
Canonical order matches ``TARGET_COLS`` in feature_compile_heating_dsm.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from sklearn.preprocessing import StandardScaler

from feature_compile_heating_dsm import TARGET_COLS

N_TARGETS = len(TARGET_COLS)  # 7


def _as_2d(y: np.ndarray) -> np.ndarray:
    arr = np.asarray(y, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError(f"expected 2-D targets, got shape {arr.shape}")
    if arr.shape[1] != N_TARGETS:
        raise ValueError(
            f"expected {N_TARGETS} target columns in order {list(TARGET_COLS)}, got {arr.shape[1]}"
        )
    return arr


@dataclass
class MultiTargetScaler:
    """Independent StandardScaler per output column (facility_kw + zones)."""

    target_cols: tuple[str, ...] = tuple(TARGET_COLS)
    _scaler: StandardScaler | None = None

    def fit(self, y: np.ndarray) -> MultiTargetScaler:
        y2 = _as_2d(y)
        self._scaler = StandardScaler()
        self._scaler.fit(y2)
        assert self._scaler.mean_ is not None and self._scaler.scale_ is not None
        if len(self._scaler.mean_) != N_TARGETS:
            raise AssertionError(f"scaler dim {len(self._scaler.mean_)} != {N_TARGETS}")
        # Avoid divide-by-zero for constant columns
        self._scaler.scale_ = np.where(self._scaler.scale_ < 1e-8, 1.0, self._scaler.scale_)
        return self

    def transform(self, y: np.ndarray) -> np.ndarray:
        if self._scaler is None:
            raise RuntimeError("MultiTargetScaler not fit")
        return self._scaler.transform(_as_2d(y))

    def inverse_transform(self, y_scaled: np.ndarray) -> np.ndarray:
        if self._scaler is None:
            raise RuntimeError("MultiTargetScaler not fit")
        out = self._scaler.inverse_transform(_as_2d(y_scaled))
        if not np.all(np.isfinite(out)):
            raise ValueError("non-finite values after inverse_transform")
        return out

    def fit_transform(self, y: np.ndarray) -> np.ndarray:
        return self.fit(y).transform(y)

    @property
    def mean_(self) -> np.ndarray:
        if self._scaler is None or self._scaler.mean_ is None:
            raise RuntimeError("MultiTargetScaler not fit")
        return np.asarray(self._scaler.mean_, dtype=np.float64)

    @property
    def scale_(self) -> np.ndarray:
        if self._scaler is None or self._scaler.scale_ is None:
            raise RuntimeError("MultiTargetScaler not fit")
        return np.asarray(self._scaler.scale_, dtype=np.float64)

    def to_dict(self) -> dict:
        return {
            "target_cols": list(self.target_cols),
            "n_targets": N_TARGETS,
            "mean": self.mean_.tolist(),
            "scale": self.scale_.tolist(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> MultiTargetScaler:
        cols = tuple(d.get("target_cols", TARGET_COLS))
        if cols != tuple(TARGET_COLS):
            raise ValueError(f"target_cols mismatch: {cols} != {TARGET_COLS}")
        obj = cls(target_cols=cols)
        sc = StandardScaler()
        sc.mean_ = np.asarray(d["mean"], dtype=np.float64)
        sc.scale_ = np.asarray(d["scale"], dtype=np.float64)
        sc.var_ = sc.scale_ ** 2
        sc.n_features_in_ = N_TARGETS
        obj._scaler = sc
        return obj


def assert_output_order(pred: np.ndarray, *, name: str = "pred") -> None:
    """Assert batch predictions are [B, 7] in TARGET_COLS order (shape only)."""
    arr = np.asarray(pred)
    if arr.ndim != 2 or arr.shape[1] != N_TARGETS:
        raise AssertionError(f"{name} shape {arr.shape} != [batch, {N_TARGETS}]")
    if not np.all(np.isfinite(arr)):
        raise AssertionError(f"{name} contains non-finite values")


def assert_target_cols(cols: Sequence[str]) -> None:
    if list(cols) != list(TARGET_COLS):
        raise AssertionError(f"target_cols {list(cols)} != canonical {list(TARGET_COLS)}")
