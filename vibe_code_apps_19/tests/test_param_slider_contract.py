"""Contract: every numeric rule parameter read from ``p`` has a sidebar slider."""

from __future__ import annotations

import ast
import inspect

from app.rules import cookbook_catalog


def _param_reads_by_function() -> dict[str, set[str]]:
    tree = ast.parse(inspect.getsource(cookbook_catalog))
    out: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        keys: set[str] = set()
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if not isinstance(child.func, ast.Name) or child.func.id != "_f":
                continue
            if len(child.args) < 2:
                continue
            param_arg, key_arg = child.args[0], child.args[1]
            if (
                isinstance(param_arg, ast.Name)
                and param_arg.id == "p"
                and isinstance(key_arg, ast.Constant)
                and isinstance(key_arg.value, str)
            ):
                keys.add(key_arg.value)
        out[node.name] = keys
    return out


def test_every_rule_param_read_has_a_cookbook_param_slider() -> None:
    reads = _param_reads_by_function()
    missing: dict[str, list[str]] = {}
    for rule in cookbook_catalog.RULES:
        # Runner substitutes weather-aware econ3_compute; catalog's econ2 callable is
        # only a declarative placeholder and its keys are intentionally irrelevant.
        if rule.id == "ECON-3":
            continue
        used = reads.get(rule.compute.__name__, set())
        exposed = {param.key for param in rule.params}
        absent = sorted(used - exposed)
        if absent:
            missing[rule.id] = absent
    assert missing == {}


def test_gl36_internal_variables_and_state_thresholds_are_exposed() -> None:
    by_id = {rule.id: {param.key for param in rule.params} for rule in cookbook_catalog.RULES}
    expected = {
        "FC1": {"eps_dsp", "eps_vfd_spd", "mode_delay_min"},
        "FC2": {"eps_mat", "eps_rat", "eps_oat", "mode_delay_min"},
        "FC3": {"eps_mat", "eps_rat", "eps_oat", "mode_delay_min"},
        "FC4": {"delta_os_max", "mode_delay_min"},
        "FC5": {"eps_sat", "eps_mat", "delta_supply_fan", "htg_on_min", "mode_delay_min"},
        "FC6": {"eps_airflow", "delta_t_min", "mode_delay_min"},
        "FC7": {"eps_sat", "htg_full_min", "mode_delay_min"},
        "FC8": {
            "eps_sat",
            "eps_mat",
            "delta_supply_fan",
            "econ_min_pos",
            "clg_inactive_max",
            "mode_delay_min",
        },
        "FC9": {
            "eps_oat",
            "eps_sat",
            "delta_supply_fan",
            "econ_min_pos",
            "clg_inactive_max",
            "mode_delay_min",
        },
        "FC10": {"eps_mat", "eps_oat", "econ_full_open", "clg_on_min", "mode_delay_min"},
        "FC11": {
            "eps_oat",
            "eps_sat",
            "delta_supply_fan",
            "econ_full_open",
            "clg_on_min",
            "mode_delay_min",
        },
        "FC12": {
            "eps_sat",
            "eps_mat",
            "delta_supply_fan",
            "econ_min_pos",
            "econ_full_open",
            "clg_on_min",
            "mode_delay_min",
        },
        "FC13": {"eps_sat", "clg_full_min", "econ_min_pos", "econ_full_open", "mode_delay_min"},
        "FC14": {
            "eps_ccet",
            "eps_cclt",
            "delta_supply_fan",
            "econ_min_pos",
            "clg_inactive_max",
            "htg_on_min",
            "mode_delay_min",
        },
        "FC15": {
            "eps_hcet",
            "eps_hclt",
            "delta_supply_fan",
            "econ_min_pos",
            "econ_full_open",
            "clg_inactive_max",
            "clg_on_min",
            "mode_delay_min",
        },
    }
    missing = {
        rule_id: sorted(required - by_id[rule_id])
        for rule_id, required in expected.items()
        if required - by_id[rule_id]
    }
    assert missing == {}
