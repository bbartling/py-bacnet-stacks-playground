"""Pickleable daily policy pack for office pretrain → field sidecar.

Sidecar may load this without EnergyPlus. It must never WriteProperty.
"""
from __future__ import annotations

import json
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from eplus_gym.rl import SCREENING_CLAIM, SCHOOL_START_STEP, SIMULATOR_REQUIRED
from eplus_gym.rl.spaces import decode_continuous, decode_discrete
from eplus_gym.six_zone_daily_controller import SixZoneDailyParams

SCHEMA = "vibe22.rl.daily_policy_pack.v1"


def _heuristic_action(obs: np.ndarray) -> np.ndarray:
    """Cold-morning → extra recovery + deeper setback. No E+ required."""
    # obs[12] = morning_min_c / 40
    morn = float(obs[12]) * 40.0 if obs.size > 12 else 0.0
    freeze_h = float(obs[13]) * 24.0 if obs.size > 13 else 0.0
    rec = 0.0
    if morn < -5.0 or freeze_h >= 8:
        rec = 180.0
    elif morn < 0.0 or freeze_h >= 4:
        rec = 120.0
    elif morn < 5.0:
        rec = 60.0
    unocc = 62.0 if morn < 0.0 else 65.0
    sb = -2.0 if morn < -5.0 else (-1.0 if morn < 0.0 else 0.0)
    return np.asarray(
        [70.0, unocc, 28.0, 68.0, rec] + [sb] * 6,
        dtype=np.float32,
    )


@dataclass
class DailyPolicyPack:
    schema: str = SCHEMA
    scientific_claim: str = SCREENING_CLAIM
    algo: str = "HEURISTIC"
    observation_dim: int = 16
    school_start_step: int = SCHOOL_START_STEP
    simulator_pretrain: str = SIMULATOR_REQUIRED
    bacnet_writes: bool = False
    sb3_zip_bytes: Optional[bytes] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def predict_action(self, obs: np.ndarray) -> np.ndarray:
        obs = np.asarray(obs, dtype=np.float32).reshape(-1)
        algo = str(self.algo).upper()
        if self.sb3_zip_bytes and algo in {"PPO", "DQN"}:
            return self._sb3_predict(obs)
        return _heuristic_action(obs)

    def _sb3_predict(self, obs: np.ndarray) -> np.ndarray:
        import tempfile

        from stable_baselines3 import DQN, PPO

        cls = PPO if str(self.algo).upper() == "PPO" else DQN
        with tempfile.TemporaryDirectory() as td:
            z = Path(td) / "policy.zip"
            z.write_bytes(self.sb3_zip_bytes or b"")
            model = cls.load(str(z), device="cpu")
            action, _ = model.predict(obs, deterministic=True)
        return np.asarray(action, dtype=np.float32).reshape(-1)

    def predict_params(self, obs: np.ndarray) -> SixZoneDailyParams:
        action = self.predict_action(obs)
        if str(self.algo).upper() == "DQN" or action.size == 1:
            return decode_discrete(int(np.asarray(action).reshape(-1)[0]))
        return decode_continuous(action)

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pickle.dumps(self, protocol=4))
        sidecar = path.with_suffix(".json")
        sidecar.write_text(
            json.dumps(
                {
                    "schema": self.schema,
                    "scientific_claim": self.scientific_claim,
                    "algo": self.algo,
                    "observation_dim": self.observation_dim,
                    "school_start_step": self.school_start_step,
                    "bacnet_writes": False,
                    "has_sb3": bool(self.sb3_zip_bytes),
                    "meta": self.meta,
                    "port": "sibling docker sidecar — proposal JSON only",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def load(path: Path) -> "DailyPolicyPack":
        obj = pickle.loads(Path(path).read_bytes())
        if not isinstance(obj, DailyPolicyPack):
            raise TypeError(f"not a DailyPolicyPack: {type(obj)}")
        return obj


def pack_from_sb3_zip(
    zip_path: Path,
    *,
    algo: str,
    meta: Dict[str, Any] | None = None,
) -> DailyPolicyPack:
    return DailyPolicyPack(
        algo=str(algo).upper(),
        sb3_zip_bytes=Path(zip_path).read_bytes(),
        meta=dict(meta or {}),
    )
