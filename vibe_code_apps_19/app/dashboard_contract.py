"""Dashboard surface freeze — UI sections + chart APIs that must not be vibe-coded away.

RCx preset ids live in ``app.rcx_plots.REQUIRED_RCX_PRESET_IDS``.
Spec: ``vibe19_agent_spec/docs/DASHBOARD_CONTRACT.md``.
"""

from __future__ import annotations

# Lazy radio sections in streamlit_app.py (do not collapse/rename without updating tests + spec).
REQUIRED_MAIN_SECTIONS: tuple[str, ...] = (
    "Overview",
    "Data & Mapping",
    "Run Rules",
    "Results by Category",
    "Plots",
    "RCx Plots",
    "Analytics",
    "Export",
)

# Public chart helpers in app/charts.py used by Plots / RCx / Analytics.
REQUIRED_CHART_APIS: tuple[str, ...] = (
    "rule_result_chart",
    "multi_equipment_timeseries",
    "multi_equipment_box",
    "oat_scatter",
    "motor_weekly_runtime_chart",
    "mech_cooling_oat_histogram",
    "max_plot_points",
    "plotly_config",
)

# Other UI entry points that must remain importable.
REQUIRED_UI_ENTRYPOINTS: tuple[str, ...] = (
    "app.ui_rcx_tab:render_rcx_plots_tab",
    "app.rcx_plots:PRESETS",
    "app.rcx_plots:REQUIRED_RCX_PRESET_IDS",
    "app.rcx_plots:collect_oat_scatter",
    "app.rcx_plots:collect_role_series",
    "app.rcx_plots:rcx_preset_coverage",
)
