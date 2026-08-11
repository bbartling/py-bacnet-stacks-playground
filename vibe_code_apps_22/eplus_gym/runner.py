"""EnergyPlus threaded runner — borrowed shape from airboxlab/rllib-energyplus.

Queues sync Python controllers with E+ zone-timestep callbacks.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class RunnerConfig:
    epw: Union[Path, str]
    idf: Union[Path, str]
    output: Union[Path, str]
    variables: Dict[str, Tuple[str, str]]
    meters: Dict[str, str]
    actuators: Dict[str, Tuple[str, str, str]]
    csv: bool = False
    verbose: bool = False
    eplus_timestep_duration: float = 0.25

    def __post_init__(self) -> None:
        self.epw = str(self.epw)
        self.idf = str(self.idf)
        self.output = str(self.output)
        for path in (self.epw, self.idf):
            if not os.path.exists(path):
                raise FileNotFoundError(path)
        if not self.actuators:
            raise ValueError("actuators required")
        if not {**self.variables, **self.meters}:
            raise ValueError("variables or meters required")


class EnergyPlusRunner:
    """Run EnergyPlus in a background thread; exchange obs/actions via queues."""

    def __init__(
        self,
        episode: int,
        obs_queue: Queue,
        act_queue: Queue,
        runner_config: RunnerConfig,
        *,
        api_cls: Any,
        exchange: Any,
    ) -> None:
        self.episode = episode
        self.runner_config = runner_config
        self.verbose = runner_config.verbose
        self.obs_queue = obs_queue
        self.act_queue = act_queue
        self.act_queue_mutex = threading.Lock()

        self.energyplus_api = api_cls()
        self.x = self.energyplus_api.exchange
        self.energyplus_exec_thread: Optional[threading.Thread] = None
        self.energyplus_state: Any = None
        self.sim_results: Dict[str, Any] = {}
        self.initialized = False
        self.progress_value = 0
        self.simulation_complete = False
        self.zone_timestep_duration = runner_config.eplus_timestep_duration

        self.variables = runner_config.variables
        self.var_handles: Dict[str, int] = {}
        self.meters = runner_config.meters
        self.meter_handles: Dict[str, int] = {}
        self.actuators = runner_config.actuators
        self.actuator_handles: Dict[str, int] = {}
        self.last_action = 0.0
        self.handle_error: Optional[str] = None

    def start(self) -> None:
        self.energyplus_state = self.energyplus_api.state_manager.new_state()
        runtime = self.energyplus_api.runtime

        # Request Output:Variable-style sensors before the run (E+ API requirement).
        for _key, (var_name, var_key) in self.variables.items():
            try:
                self.x.request_variable(self.energyplus_state, var_name, var_key)
            except Exception:  # noqa: BLE001
                pass

        def _report_progress(progress: int) -> None:
            self.progress_value = progress
            if self.verbose:
                print(f"Simulation progress: {self.progress_value}%")

        runtime.callback_progress(self.energyplus_state, _report_progress)
        runtime.set_console_output_status(self.energyplus_state, self.verbose)
        runtime.callback_end_zone_timestep_after_zone_reporting(
            self.energyplus_state, self._collect_obs
        )
        runtime.callback_after_predictor_after_hvac_managers(
            self.energyplus_state, self._send_actions
        )

        def _run_energyplus(rn, cmd_args, state, results):
            results["exit_code"] = rn.run_energyplus(state, cmd_args)
            if not self.simulation_complete:
                self.obs_queue.put(None)
                self.act_queue.put(None)
                self.stop()

        self.energyplus_exec_thread = threading.Thread(
            target=_run_energyplus,
            args=(
                self.energyplus_api.runtime,
                self.make_eplus_args(),
                self.energyplus_state,
                self.sim_results,
            ),
        )
        self.energyplus_exec_thread.start()

    def stop(self) -> None:
        if not self.simulation_complete:
            self.simulation_complete = True
            self._flush_queues()
        if self.energyplus_exec_thread:
            try:
                self.energyplus_exec_thread.join(timeout=120)
            except RuntimeError:
                pass
            self.energyplus_exec_thread = None
        try:
            self.energyplus_api.runtime.clear_callbacks()
            self.energyplus_api.state_manager.delete_state(self.energyplus_state)
        except Exception:  # noqa: BLE001
            pass

    def failed(self) -> bool:
        return self.sim_results.get("exit_code", -1) > 0

    def make_eplus_args(self) -> List[str]:
        eplus_args = ["-r"] if self.runner_config.csv else []
        out = Path(self.runner_config.output) / f"episode-{self.episode:08}-{os.getpid():05}"
        out.mkdir(parents=True, exist_ok=True)
        eplus_args += [
            "-w",
            self.runner_config.epw,
            "-d",
            str(out),
            self.runner_config.idf,
        ]
        return eplus_args

    def init_exchange(self, default_action: float) -> Dict[str, float]:
        self.last_action = float(default_action)
        self.act_queue.put(self.last_action)
        return self.obs_queue.get()

    def _collect_obs(self, state_argument) -> None:
        try:
            if self.simulation_complete or not self._init_callback(state_argument):
                return
            self.next_obs = {
                **{
                    key: (
                        self.x.get_variable_value(state_argument, handle)
                        if handle != -1
                        else float("nan")
                    )
                    for key, handle in self.var_handles.items()
                },
                **{
                    key: (
                        self.x.get_meter_value(state_argument, handle)
                        if handle != -1
                        else float("nan")
                    )
                    for key, handle in self.meter_handles.items()
                },
            }
            self.obs_queue.put(self.next_obs)
        except Exception as exc:  # noqa: BLE001 — never raise into ctypes
            self.handle_error = str(exc)
            self.simulation_complete = True
            try:
                self.obs_queue.put(None)
            except Exception:  # noqa: BLE001
                pass

    def _send_actions(self, state_argument) -> None:
        try:
            if self.simulation_complete or not self._init_callback(state_argument):
                return
            if self.handle_error:
                return
            sys_timestep_duration = self.x.system_time_step(state_argument)
            if (
                sys_timestep_duration < self.zone_timestep_duration
                and self.act_queue.empty()
            ):
                self.act_queue.put(self.last_action)
            with self.act_queue_mutex:
                if self.simulation_complete:
                    return
                next_action = self.act_queue.get()
            if next_action is None:
                self.simulation_complete = True
                return
            self.last_action = float(next_action)
            handle = list(self.actuator_handles.values())[0]
            if handle == -1:
                return
            self.x.set_actuator_value(
                state=state_argument,
                actuator_handle=handle,
                actuator_value=self.last_action,
            )
        except Exception as exc:  # noqa: BLE001 — never raise into ctypes
            self.handle_error = str(exc)
            self.simulation_complete = True
            try:
                self.obs_queue.put(None)
            except Exception:  # noqa: BLE001
                pass

    def _init_callback(self, state_argument) -> bool:
        ok = self._init_handles(state_argument)
        if not ok or self.handle_error:
            return False
        return not self.x.warmup_flag(state_argument)

    def _init_handles(self, state_argument) -> bool:
        if self.initialized:
            return True
        if not self.x.api_data_fully_ready(state_argument):
            return False
        for _key, (var_name, var_key) in self.variables.items():
            try:
                self.x.request_variable(state_argument, var_name, var_key)
            except Exception:  # noqa: BLE001
                pass
        self.var_handles = {
            key: self.x.get_variable_handle(state_argument, *var)
            for key, var in self.variables.items()
        }
        self.meter_handles = {
            key: self.x.get_meter_handle(state_argument, meter)
            for key, meter in self.meters.items()
        }
        self.actuator_handles = {
            key: self.x.get_actuator_handle(state_argument, *actuator)
            for key, actuator in self.actuators.items()
        }
        # Actuators are required; sensors may be NaN if IDF lacks Output:Variable/Meter.
        if any(v == -1 for v in self.actuator_handles.values()):
            available = self.x.list_available_api_data_csv(state_argument).decode(
                "utf-8", errors="replace"
            )
            self.handle_error = (
                f"got -1 actuator handle; check names.\n"
                f"variables={self.var_handles}\n"
                f"meters={self.meter_handles}\n"
                f"actuators={self.actuator_handles}\n"
                f"available:\n{available[:4000]}"
            )
            return False
        missing_sensors = {
            **{k: v for k, v in self.var_handles.items() if v == -1},
            **{k: v for k, v in self.meter_handles.items() if v == -1},
        }
        if missing_sensors and self.verbose:
            print(f"WARN missing E+ sensor handles (NaN obs): {missing_sensors}")
        self.initialized = True
        return True

    def _flush_queues(self) -> None:
        if self.act_queue.empty():
            self.act_queue.put(None)
        while not self.obs_queue.empty():
            try:
                self.obs_queue.get_nowait()
            except Empty:
                break
        with self.act_queue_mutex:
            while not self.act_queue.empty():
                try:
                    self.act_queue.get_nowait()
                except Empty:
                    break
