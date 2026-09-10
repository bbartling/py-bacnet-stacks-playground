"""Vibe 25 — Open-FDD PID-HUNT-1 tutorial helpers."""

from .detect import fault_summary, run_pid_hunt
from .plotting import plot_healthy_vs_hunting, plot_valve_overview, plot_valve_zoom_with_tv
from .synth import (
    COLUMN,
    POLL_SECONDS,
    healthy_cooling_valve,
    hunting_cooling_valve,
    hunting_midrange_sine_cooling_valve,
    hunting_sine_cooling_valve,
)

__version__ = "0.1.0"

__all__ = [
    "COLUMN",
    "POLL_SECONDS",
    "fault_summary",
    "healthy_cooling_valve",
    "hunting_cooling_valve",
    "hunting_midrange_sine_cooling_valve",
    "hunting_sine_cooling_valve",
    "plot_healthy_vs_hunting",
    "plot_valve_overview",
    "plot_valve_zoom_with_tv",
    "run_pid_hunt",
]
