"""BACnet-style priority array point bus."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PointKind(str, Enum):
    SENSOR = "sensor"
    COMMANDABLE = "commandable"


@dataclass
class PointDef:
    name: str
    kind: PointKind
    description: str
    units: str = ""
    default: float = 0.0
    binary: bool = False


@dataclass
class PointState:
    definition: PointDef
    # BACnet priorities 1..16 → index 0..15
    priority_values: list[float | None] = field(default_factory=lambda: [None] * 16)
    priority_sources: list[str | None] = field(default_factory=lambda: [None] * 16)
    sensor_value: float = 0.0

    def present_value(self) -> float:
        if self.definition.kind is PointKind.SENSOR:
            return float(self.sensor_value)
        for value in self.priority_values:
            if value is not None:
                return float(value)
        return float(self.definition.default)

    def winning_priority(self) -> int | None:
        if self.definition.kind is PointKind.SENSOR:
            return None
        for idx, value in enumerate(self.priority_values):
            if value is not None:
                return idx + 1
        return None

    def winning_source(self) -> str | None:
        if self.definition.kind is PointKind.SENSOR:
            return "plant"
        for idx, value in enumerate(self.priority_values):
            if value is not None:
                return self.priority_sources[idx] or "unknown"
        return "default"


class PointBus:
    """Shared present-value store for BACnet + UI."""

    def __init__(self, definitions: list[PointDef]):
        self._points: dict[str, PointState] = {}
        for definition in definitions:
            state = PointState(definition=definition, sensor_value=float(definition.default))
            if definition.kind is PointKind.COMMANDABLE:
                # Seed priority 16 with default so the plant always sees a value.
                state.priority_values[15] = float(definition.default)
                state.priority_sources[15] = "default"
            self._points[definition.name] = state

    def names(self) -> list[str]:
        return list(self._points.keys())

    def get(self, name: str) -> PointState:
        try:
            return self._points[name]
        except KeyError as exc:
            raise KeyError(f"unknown point {name!r}") from exc

    def present(self, name: str) -> float:
        return self.get(name).present_value()

    def snapshot(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name, state in self._points.items():
            rows.append(
                {
                    "name": name,
                    "kind": state.definition.kind.value,
                    "description": state.definition.description,
                    "units": state.definition.units,
                    "binary": state.definition.binary,
                    "present_value": state.present_value(),
                    "winning_priority": state.winning_priority(),
                    "winning_source": state.winning_source(),
                    "priority_array": list(state.priority_values),
                }
            )
        return rows

    def write(self, name: str, value: float, *, priority: int = 8, source: str = "ui") -> float:
        state = self.get(name)
        if state.definition.kind is not PointKind.COMMANDABLE:
            raise ValueError(f"{name} is not commandable")
        if not 1 <= int(priority) <= 16:
            raise ValueError("priority must be 1..16")
        idx = int(priority) - 1
        state.priority_values[idx] = float(value)
        state.priority_sources[idx] = str(source)
        return state.present_value()

    def relinquish(self, name: str, *, priority: int = 8) -> float:
        state = self.get(name)
        if state.definition.kind is not PointKind.COMMANDABLE:
            raise ValueError(f"{name} is not commandable")
        if not 1 <= int(priority) <= 16:
            raise ValueError("priority must be 1..16")
        idx = int(priority) - 1
        state.priority_values[idx] = None
        state.priority_sources[idx] = None
        return state.present_value()

    def set_sensor(self, name: str, value: float) -> None:
        state = self.get(name)
        if state.definition.kind is not PointKind.SENSOR:
            raise ValueError(f"{name} is not a sensor")
        state.sensor_value = float(value)

    def commands(self) -> dict[str, float]:
        return {
            name: state.present_value()
            for name, state in self._points.items()
            if state.definition.kind is PointKind.COMMANDABLE
        }
