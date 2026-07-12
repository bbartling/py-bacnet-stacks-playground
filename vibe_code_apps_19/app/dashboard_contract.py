"""Frozen UI sections / chart APIs — do not vibe-code away without updating the spec."""

from __future__ import annotations

# Lazy radio sections in streamlit_app.py (do not collapse/rename without updating tests + spec).
REQUIRED_MAIN_SECTIONS: tuple[str, ...] = (
    "Overview",
    "Data Model",
    "Run Rules",
    "Results by Category",
    "Plots",
    "RCx Plots",
    "Metering",
    "Export",
)

# Public chart helpers in app/charts.py used by Plots / RCx / Overview / Metering.
REQUIRED_CHART_APIS: tuple[str, ...] = (
    "rule_result_chart",
    "multi_equipment_timeseries",
    "multi_equipment_box",
    "oat_scatter",
    "motor_weekly_runtime_chart",
    "mech_cooling_oat_histogram",
    "bas_vs_web_oat_histogram",
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
    "app.rcx_plots:pump_mode_summary_bundle",
    "app.data_model_tree:build_data_model_tree",
    "app.rule_card:build_rule_card",
    "app.docx_report:build_equipment_fdd_docx",
    "app.docx_report:build_building_data_model_docx",
    "app.docx_report:build_analytics_docx",
    "app.docx_report:build_rcx_catalog_docx",
    "app.docx_report:build_session_docx_pack",
    "app.docx_report:build_fdd_by_system_docx",
)
