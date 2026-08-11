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
        self.default_action = float(self.post_process_action(self.action_space.sample()))

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

    def post_process_action(self, action: Union[float, List[float], np.ndarray]) -> float:
        if isinstance(action, (list, tuple, np.ndarray)):
            return float(np.asarray(action).reshape(-1)[0])
        return float(action)

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None):
        super().reset(seed=seed)
        self.episode += 1
        self.timestep = 0
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
        self.last_obs = obs
        return np.array(list(obs.values()), dtype=np.float32), {
            "honesty": self.honesty,
            "provenance": self.provenance,
            "promote": self.promote,
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
            timeout = float(self.env_config.get("queue_timeout_s", 30.0))
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
        obs_vec = np.array(list(obs.values()), dtype=np.float32)
        info = {
            "honesty": self.honesty,
            "provenance": self.provenance,
            "obs_dict": obs,
            "action_c": float(self.post_process_action(action)),
        }
        return obs_vec, float(reward), done, truncated, info

    def close(self):
        if self.energyplus_runner is not None:
            self.energyplus_runner.stop()
            self.energyplus_runner = None
