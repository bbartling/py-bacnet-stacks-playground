"""EnergyPlus threaded runner — Lakeside multi-actuator patch on rleplus.

His Amphitheater runner asserts a single float actuator. Six DualSP needs a
vector send + Electricity:Facility meter-index 0 workaround.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any, Dict, List, Optional, Tuple, Union

def _meter_lookup_key(name: str) -> str:
    return str(name).split("[", 1)[0].strip().upper()


def _meter_indices_from_api_csv(raw: Union[bytes, str]) -> Dict[str, int]:
    """Map meter names to 0-based handles from list_available_api_data_csv."""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    indices: Dict[str, int] = {}
    in_meters = False
    idx = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "**METERS**":
            in_meters = True
            continue
        if in_meters and stripped.startswith("**"):
            break
        if in_meters and stripped.upper().startswith("OUTPUTMETER,"):
            parts = stripped.split(",")
            if len(parts) >= 2:
                indices[_meter_lookup_key(parts[1])] = idx
                idx += 1
    return indices


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
    """Run EnergyPlus in a background thread; exchange obs/actions via queues.

    Lakeside patch on airboxlab/rllib-energyplus: six DualSP actuators +
    Electricity:Facility meter index 0. Do not import his EnergyPlusRunner
    (it loads pyenergyplus at module import).
    """

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
        self.actuator_order: List[str] = list(self.actuators.keys())
        self.last_action: Any = 0.0
        self.last_applied: Dict[str, float] = {}
        self.handle_error: Optional[str] = None
        self.multi_actuator = len(self.actuator_order) > 1

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

    def init_exchange(self, default_action: Any) -> Dict[str, float]:
        self.last_action = self._normalize_action(default_action)
        self.act_queue.put(self.last_action)
        return self.obs_queue.get()

    def _normalize_action(self, action: Any) -> Any:
        """Scalar for 1 actuator; length-N list for multi-actuator envs."""
        n = len(self.actuator_order)
        if n <= 1:
            if isinstance(action, (list, tuple)):
                return float(action[0])
            arr = getattr(action, "reshape", None)
            if arr is not None:
                return float(action.reshape(-1)[0])
            return float(action)
        vals = list(action) if not isinstance(action, (float, int)) else [float(action)] * n
        if hasattr(action, "reshape") and not isinstance(action, (list, tuple)):
            vals = [float(x) for x in action.reshape(-1)]
        elif isinstance(action, (list, tuple)):
            vals = [float(x) for x in action]
        if len(vals) != n:
            raise ValueError(f"expected {n} actions, got {len(vals)}")
        if any(v != v or v in (float("inf"), float("-inf")) for v in vals):
            raise ValueError(f"non-finite action values: {vals}")
        return vals

    def _runtime_calendar(self, state_argument) -> Dict[str, float]:
        """Actual EnergyPlus Runtime calendar (not synthetic step dating)."""
        kind = int(self.x.kind_of_sim(state_argument))
        warmup = bool(self.x.warmup_flag(state_argument))
        return {
            "ep_year": float(self.x.year(state_argument)),
            "ep_month": float(self.x.month(state_argument)),
            "ep_day": float(self.x.day_of_month(state_argument)),
            "ep_hour": float(self.x.hour(state_argument)),
            "ep_minute": float(self.x.minutes(state_argument)),
            "kind_of_sim": float(kind),
            "warmup": 1.0 if warmup else 0.0,
        }

    def _collect_obs(self, state_argument) -> None:
        try:
            if self.simulation_complete or not self._init_callback(state_argument):
                return
            # Hard gate: only RunPeriodWeather (3), never sizing/design-day.
            kind = int(self.x.kind_of_sim(state_argument))
            if kind != 3 or bool(self.x.warmup_flag(state_argument)):
                return
            applied = {}
            for key, handle in self.actuator_handles.items():
                if handle == -1:
                    applied[f"applied_{key}"] = float("nan")
                    continue
                try:
                    applied[f"applied_{key}"] = float(
                        self.x.get_actuator_value(state_argument, handle)
                    )
                except Exception:  # noqa: BLE001
                    applied[f"applied_{key}"] = float("nan")
            self.last_applied = applied
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
                **applied,
                **self._runtime_calendar(state_argument),
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
            kind = int(self.x.kind_of_sim(state_argument))
            if kind != 3 or bool(self.x.warmup_flag(state_argument)):
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
            try:
                self.last_action = self._normalize_action(next_action)
            except ValueError as exc:
                self.handle_error = str(exc)
                self.simulation_complete = True
                return
            # Fail on missing/duplicate handles
            handles = [self.actuator_handles[k] for k in self.actuator_order]
            if any(h == -1 for h in handles):
                self.handle_error = f"missing actuator handle: {self.actuator_handles}"
                self.simulation_complete = True
                return
            if len(set(handles)) != len(handles):
                self.handle_error = f"duplicate actuator handles: {self.actuator_handles}"
                self.simulation_complete = True
                return
            if self.multi_actuator:
                vals = list(self.last_action)
                for key, val in zip(self.actuator_order, vals):
                    self.x.set_actuator_value(
                        state=state_argument,
                        actuator_handle=self.actuator_handles[key],
                        actuator_value=float(val),
                    )
            else:
                key = self.actuator_order[0]
                self.x.set_actuator_value(
                    state=state_argument,
                    actuator_handle=self.actuator_handles[key],
                    actuator_value=float(self.last_action),
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
        meter_index = None
        self.meter_handles = {}
        for key, meter in self.meters.items():
            handle = self.x.get_meter_handle(state_argument, meter)
            if handle == -1:
                # EnergyPlus getMeterHandle treats meter index 0 as missing
                # (Electricity:Facility is usually 0). Fall back to API CSV order.
                if meter_index is None:
                    meter_index = _meter_indices_from_api_csv(
                        self.x.list_available_api_data_csv(state_argument)
                    )
                handle = meter_index.get(_meter_lookup_key(meter), -1)
            self.meter_handles[key] = handle
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
        # kind_of_sim: 1=DesignDay, 2=RunPeriodDesign, 3=RunPeriodWeather
        # Never initialize / score during sizing or warmup — even if sensors resolve.
        kind = int(self.x.kind_of_sim(state_argument))
        warmup = bool(self.x.warmup_flag(state_argument))
        if kind != 3 or warmup:
            return False
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
