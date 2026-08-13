#!/usr/bin/env python3
"""Fail fast if Streamlit entry imports are broken (run before launching UI)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    checks = [
        ("eplus_gym.controllers", ("RuleController", "effective_htg_setpoints_f")),
        ("eplus_gym_app.plots", ("eui_peer_bullet_figure", "dsm_panel_figure")),
        ("eplus_gym_app.site_config", ("load_site_dsm_config", "render_site_config_tab")),
        ("eplus_gym_app.dsm_console", ("strategy_library", "render_run_dsm_tab")),
        ("eplus_gym_app.streamlit_app", ("main",)),
    ]
    for mod_name, attrs in checks:
        mod = importlib.import_module(mod_name)
        for attr in attrs:
            if not hasattr(mod, attr):
                print(f"FAIL: {mod_name}.{attr} missing", file=sys.stderr)
                return 1
            print(f"ok {mod_name}.{attr}")
    # Smoke strategy library with Site Config overrides
    from eplus_gym_app.dsm_console import strategy_library

    rows = strategy_library(
        {"setpoints_f": {"occupied_heating_f": 70.0, "unoccupied_heating_f": 55.0}}
    )["rows"]
    base = next(r for r in rows if r["strategy_id"] == "baseline")
    if float(base["unocc_htg_sp_f"]) != 55.0:
        print(f"FAIL: baseline unocc expected 55 got {base['unocc_htg_sp_f']}", file=sys.stderr)
        return 1
    print("ok strategy_library site override")
    print("ALL IMPORT SMOKES PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
