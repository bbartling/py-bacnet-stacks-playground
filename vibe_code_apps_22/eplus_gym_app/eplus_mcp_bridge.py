"""EnergyPlus-MCP agent bridge notes (Cursor MCP ``user-energyplus``).

Runtime Streamlit / gym paths stay on CLI + ``eplus_native`` patches. MCP has
**no** setpoint-write tool for live ``SCH_HtgSP`` actuators — use Site Config
+ staged IDF patches instead.

Use MCP for inspect / RunPeriod / validate work during agent sessions:

- ``check_simulation_settings`` - RunPeriod vs weather
- ``modify_run_period`` - on a **copy** of the IDF only
- ``inspect_schedules`` - SCH_HtgSP / SCH_ClgSP / occupancy
- ``list_zones`` / ``validate_idf`` - pack sanity
- ``get_model_summary`` - building name / zone count

Do **not** replace ``run_eplus_gym_rules`` / campaign supervisor with MCP for
closed-loop DSM steps.
"""
from __future__ import annotations

from typing import Any

# Documented tool names for agent checklists (not live MCP bindings).
MCP_INSPECT_TOOLS: tuple[str, ...] = (
    "check_simulation_settings",
    "modify_run_period",
    "inspect_schedules",
    "list_zones",
    "validate_idf",
    "get_model_summary",
    "get_output_variables",
    "get_output_meters",
)

MCP_LESSONS: dict[str, Any] = {
    "winter_amy_data_periods": (
        "Multi-year AMY EPW DATA PERIODS must use mm/dd/yyyy. Month/day-only "
        "tokens (e.g. 8/1,8/7) make EnergyPlus report a noyear Aug window and "
        "reject winter RunPeriods like 2026-01-26. Staged RunPeriods with years "
        "must Treat Weather as Actual=Yes so E+ uses absolute multi-year coverage."
    ),
    "staged_only_setpoints": (
        "Site Config setpoints patch SCH_HtgSP/SCH_ClgSP on staged run IDFs only. "
        "Never overwrite the published champion IDF."
    ),
    "mcp_vs_runtime": (
        "MCP is for agent inspect/RunPeriod/validate. Streamlit live DSM stays on "
        "CLI gym + eplus_native. MCP cannot write live SCH_HtgSP actuators."
    ),
}


def mcp_agent_checklist() -> list[str]:
    """Short ordered checklist for agents debugging winter sims / schedules."""
    return [
        "repair_epw_data_periods / confirm DATA PERIODS is year-aware",
        "MCP check_simulation_settings on staged IDF + EPW",
        "MCP inspect_schedules for SCH_HtgSP / SCH_ClgSP",
        "MCP modify_run_period only on a copy (never champion)",
        "MCP validate_idf / list_zones",
        "Run DSM via campaign supervisor (not MCP) for closed-loop steps",
    ]
