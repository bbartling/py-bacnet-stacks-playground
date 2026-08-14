"""Gymnasium EnergyPlusEnv base — shape from airboxlab/rllib-energyplus."""
from __future__ import annotations

import abc
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any, Dict, List, Optional, Tuple, Union

import gymnasium as gym
import numpy as np

from .discover import try_import_energyplus_api
from .honesty import HONESTY_IDEALLOADS, PROMOTE, PROVENANCE_LIVE
from .runner import EnergyPlusRunner, RunnerConfig


class EnergyPlusEnv(gym.Env, metaclass=abc.ABCMeta):
    """Abstract E+ gym. Subclass for Lakeside IdealLoads / future W2A."""

    metadata = {"render_modes": []}

    def __init__(self, env_config: Dict[str, Any]):
        super().__init__()
        self.env_config = env_config
        self.episode = -1
        self.timestep = 0
        self.honesty = env_config.get("honesty", HONESTY_IDEALLOADS)
        self.promote = PROMOTE
        self.provenance = PROVENANCE_LIVE

        self.observation_space = self.get_observation_space()
        self.action_space = self.get_action_space()
        self.last_obs: Dict[str, float] = {}
        self._obs_keys: List[str] = []
        # Deterministic init — never action_space.sample().
        self.default_action = self._resolve_default_action(env_config)
        self.default_action_provenance = {
            "default_action": (
                list(self.default_action)
                if isinstance(self.default_action, (list, tuple, np.ndarray))
                else float(self.default_action)
            ),
            "source": str(env_config.get("default_action_source") or "baseline_70F"),
        }

        self.energyplus_runner: Optional[EnergyPlusRunner] = None
        self.obs_queue: Optional[Queue] = None
        self.act_queue: Optional[Queue] = None

        api_cls, _exchange, root = try_import_energyplus_api()
        self._api_cls = api_cls
        self._eplus_root = root

        self.runner_config = RunnerConfig(
            epw=self.get_weather_file(),
            idf=self.get_idf_file(),
            output=self.env_config["output"],
            variables=self.get_variables(),
            meters=self.get_meters(),
            actuators=self.get_actuators(),
            csv=bool(self.env_config.get("csv", False)),
            verbose=bool(self.env_config.get("verbose", False)),
            eplus_timestep_duration=float(
                self.env_config.get("eplus_timestep_duration", 0.25)
            ),
        )

    @abc.abstractmethod
    def get_weather_file(self) -> Union[Path, str]:
        ...

    @abc.abstractmethod
    def get_idf_file(self) -> Union[Path, str]:
        ...

    @abc.abstractmethod
    def get_observation_space(self) -> gym.Space:
        ...

    @abc.abstractmethod
    def get_action_space(self) -> gym.Space:
        ...

    @abc.abstractmethod
    def compute_reward(self, obs: Dict[str, float]) -> float:
        ...

    @abc.abstractmethod
    def get_variables(self) -> Dict[str, Tuple[str, str]]:
        ...

    @abc.abstractmethod
    def get_meters(self) -> Dict[str, str]:
        ...

    @abc.abstractmethod
    def get_actuators(self) -> Dict[str, Tuple[str, str, str]]:
        ...

    def _resolve_default_action(self, env_config: Dict[str, Any]):
        if "default_action_c" in env_config:
            env_config.setdefault("default_action_source", "env_config.default_action_c")
            return self.post_process_action(env_config["default_action_c"])
        if "occupied_heating_f" in env_config:
            env_config.setdefault("default_action_source", "env_config.occupied_heating_f")
            occ_c = (float(env_config["occupied_heating_f"]) - 32.0) * 5.0 / 9.0
            n = int(np.prod(self.action_space.shape)) if self.action_space.shape else 1
            if n > 1:
                return self.post_process_action([occ_c] * n)
            return self.post_process_action(occ_c)
        env_config.setdefault("default_action_source", "baseline_70F")
        n = int(np.prod(self.action_space.shape)) if self.action_space.shape else 1
        if n > 1:
            return self.post_process_action([21.11111111111111] * n)
        return self.post_process_action(21.11111111111111)

    def post_process_action(self, action: Union[float, List[float], np.ndarray]):
        """Preserve vector actions when action_space is multi-dimensional."""
        n = int(np.prod(self.action_space.shape)) if getattr(self, "action_space", None) else 1
        if n <= 1:
            if isinstance(action, (list, tuple, np.ndarray)):
                return float(np.asarray(action).reshape(-1)[0])
            return float(action)
        arr = np.asarray(action, dtype=np.float32).reshape(-1)
        if arr.size == 1:
            arr = np.full((n,), float(arr[0]), dtype=np.float32)
        if arr.size != n:
            raise ValueError(f"action length {arr.size} != action_space {n}")
        if not np.isfinite(arr).all():
            raise ValueError(f"non-finite action: {arr}")
        return arr.astype(np.float32)

    def _obs_vector(self, obs: Dict[str, float]) -> np.ndarray:
        if not self._obs_keys:
            self._obs_keys = list(obs.keys())
        return np.array([float(obs.get(k, float("nan"))) for k in self._obs_keys], dtype=np.float32)

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None):
        super().reset(seed=seed)
        self.episode += 1
        self.timestep = 0
        self._obs_keys = []
        if self.energyplus_runner is not None:
            self.energyplus_runner.stop()

        self.obs_queue = Queue(maxsize=1)
        self.act_queue = Queue(maxsize=1)
        self.energyplus_runner = EnergyPlusRunner(
            episode=self.episode,
            obs_queue=self.obs_queue,
            act_queue=self.act_queue,
            runner_config=self.runner_config,
            api_cls=self._api_cls,
            exchange=None,
        )
        self.energyplus_runner.start()
        obs = self.energyplus_runner.init_exchange(default_action=self.default_action)
        if obs is None:
            from .errors import EnergyPlusStartupError
            from .startup_diag import diagnose_startup_failure

            diag = diagnose_startup_failure(self.energyplus_runner)
            try:
                self.energyplus_runner.stop()
            except Exception:  # noqa: BLE001
                pass
            raise EnergyPlusStartupError(
                diag["message"],
                exit_code=diag.get("exit_code"),
                runner_error=diag.get("runner_error"),
                err_path=diag.get("err_path"),
                severe_or_fatal=diag.get("severe_or_fatal"),
                log_tail=diag.get("log_tail"),
                details=diag,
            )
        self.last_obs = obs
        return self._obs_vector(obs), {
            "honesty": self.honesty,
            "provenance": self.provenance,
            "promote": self.promote,
            "default_action": self.default_action_provenance,
            "obs_dict": obs,
        }

    def step(self, action):
        self.timestep += 1
        done = False
        truncated = False
        if self.energyplus_runner is None:
            raise RuntimeError("call reset() first")
        if self.energyplus_runner.failed():
            raise RuntimeError(
                f"EnergyPlus failed exit={self.energyplus_runner.sim_results.get('exit_code')}"
            )
        if getattr(self.energyplus_runner, "handle_error", None):
            raise RuntimeError(self.energyplus_runner.handle_error)
        if self.energyplus_runner.simulation_complete:
            done = True
            obs = self.last_obs
        else:
            action_to_apply = self.post_process_action(action)
            timeout = float(self.env_config.get("queue_timeout_s", 120.0))
            try:
                self.act_queue.put(action_to_apply, timeout=timeout)
                obs = self.obs_queue.get(timeout=timeout)
            except (Full, Empty):
                obs = None
            if obs is None:
                done = True
                obs = self.last_obs
            else:
                self.last_obs = obs

        reward = self.compute_reward(obs)
        applied = self.post_process_action(action)
        info = {
            "honesty": self.honesty,
            "provenance": self.provenance,
            "obs_dict": obs,
            "action": (
                [float(x) for x in applied]
                if isinstance(applied, np.ndarray)
                else float(applied)
            ),
        }
        return self._obs_vector(obs), float(reward), done, truncated, info

    def close(self):
        if self.energyplus_runner is not None:
            self.energyplus_runner.stop()
            self.energyplus_runner = None
