"""Generate vibe19_agent_spec/docs/RULE_PLOT_CATALOG.md from the live catalog."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from app.column_map_json import COOKBOOK_TO_HAYSTACK_POINT, FAMILY_LABELS, FAMILY_ORDER
from app.rules.cookbook_catalog import RULES
from app.rules.operational_gate import RULE_GATES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "vibe19_agent_spec" / "docs" / "RULE_PLOT_CATALOG.md"

# Preferred Haystack names for roles missing from COOKBOOK_TO_HAYSTACK_POINT
# (kept for generator resilience; prefer extending COOKBOOK_TO_HAYSTACK_POINT instead).
EXTENDED_HS = {
    "fan_speed_feedback": "fan-speed-feedback",
    "fan_current": "fan-current",
    "fan_power": "fan-power",
    "airflow_proof": "airflow-proof",
    "pump_status": "pump-status",
    "compressor_status": "compressor-status",
    "dx_stage": "dx-stage",
    "dx_cool_cmd": "dx-cool-cmd",
    "cool_stage": "cool-stage",
    "dx_cooling": "dx-cooling",
}

ANALYTICS_HINTS = {
    "SV-RANGE": "Plots sensor-fault summary stats when FAULT; Export sensor fault CSV.",
    "SV-FLATLINE": "Plots sensor-fault summary stats when FAULT.",
    "SV-SPIKE": "Plots sensor-fault summary stats when FAULT.",
    "SV-STALE": "Plots sensor-fault summary stats when FAULT.",
    "SCHED-1": "Overview occupancy calendar drives `occ_mode`; zone comfort band sliders (°F/°C display).",
    "OAT-METEO": "Needs both BAS `oa_t` and web `wx_oa_t`; Prefer web OAT sidebar.",
    "ECON-3": "Free-cool uses web dry-bulb + dewpoint (RH→Magnus); related to mech-cooling OAT bins (DX/plant only).",
    "CW-OPT-1": "RCx `cw_reset_scatter` uses `cw_supply_t` vs web wet-bulb.",
    "CHW-1": "RCx `chw_reset_scatter` — CHW leave vs web OAT; motor weekly uses pump/status not leave-temp.",
    "CHW-2": "Plant motor weekly / chiller runtime — status/pump proof.",
    "AHU-DUCTHI": "RCx `duct_static_box` (fan-on) for static-reset opportunity.",
    "AHU-SATDEV": "RCx `ahu_sat_reset_scatter` — SAT vs web OAT.",
    "TRIM-1": "Duct static / pressure trim requests; related to duct-static box RCx.",
    "TRIM-3": "HW reset requests; RCx `hw_reset_scatter`.",
    "TRIM-4": "CHW reset requests; RCx `chw_reset_scatter`.",
    "VLV-1": "Valve closed + SAT vs SP **or** SAT vs MAT; fan gate when present.",
    "FC6": "Needs AHU `vav_total_flow` — empty plots often data gaps.",
    "ECON-1": "Needs OA damper / MAT / OAT roles (`oa_damper_pct` e.g. mad_c).",
    "ECON-2": "Needs OA damper / MAT / OAT roles.",
    "ECON-4": "Needs OA damper / MAT / OAT roles.",
    "ECON-5": "Needs heat/preheat roles.",
    "WX-1": "Weather family; web OAT enrich on weather frame.",
    "HP-1": "Mech-cooling OAT bins can use DX/compressor roles.",
}


def haystack(role: str) -> str:
    if role in COOKBOOK_TO_HAYSTACK_POINT:
        return COOKBOOK_TO_HAYSTACK_POINT[role]
    if role in EXTENDED_HS:
        return EXTENDED_HS[role]
    return role.replace("_", "-")


def role_row(role: str, req: str) -> str:
    return f"| `{role}` | `{haystack(role)}` | {req} |"


def main() -> None:
    lines: list[str] = []
    L = lines.append

    L("# Rule plot catalog (all 50)")
    L("")
    L("**Audience:** agents / engineers reviewing **Plots** validation cards and FDD DOCX.")
    L("")
    L("One section per cookbook rule, grouped by **mechanical family** (same order as sidebar / Results).")
    L(
        "Each chart plots **required (+ optional) roles** present on the mapped frame, "
        "plus a **confirmed-fault swim lane**."
    )
    L("")
    L("| Source | Path |")
    L("| --- | --- |")
    L("| Catalog | `app/rules/cookbook_catalog.py` |")
    L("| Haystack export map | `app/column_map_json.py` → `COOKBOOK_TO_HAYSTACK_POINT` |")
    L("| Gates | `app/rules/operational_gate.py` → `RULE_GATES` |")
    L("| Chart API | `app/charts.py` → `rule_result_chart` |")
    L("| UX contract | [`PLOTS_DOCX_VALIDATION.md`](PLOTS_DOCX_VALIDATION.md) |")
    L("| Machine inventory | `configs/rule_inventory.yaml` (regenerate: `scripts/generate_rule_configs.py`) |")
    L("")
    L("**Haystack note:** Preferred tags come from `COOKBOOK_TO_HAYSTACK_POINT`. Roles not in that dict")
    L("use the extended names in Appendix B (hyphenated Project Haystack–style).")
    L("")
    L("**Sliders:** sidebar **Rule tuning** by category; values live in `session_state.params[rule_id]`.")
    L("Confirm delay is usually `confirm_min` (minutes) even when catalog `confirm_seconds` differs.")
    L("")
    L("---")
    L("")
    L("## Index by family")
    L("")
    L("| Family | Count | Rule ids |")
    L("| --- | ---: | --- |")

    by_fam: dict[str, list] = defaultdict(list)
    for r in RULES:
        by_fam[r.family].append(r)

    for fam in FAMILY_ORDER:
        rules = by_fam.get(fam) or []
        if not rules:
            continue
        ids = ", ".join(f"`{r.id}`" for r in rules)
        L(f"| {FAMILY_LABELS.get(fam, fam)} | {len(rules)} | {ids} |")

    n = sum(len(by_fam[f]) for f in FAMILY_ORDER if by_fam.get(f))
    assert n == 50, n

    for fam in FAMILY_ORDER:
        rules = by_fam.get(fam) or []
        if not rules:
            continue
        L("")
        L("---")
        L("")
        L(f"## {FAMILY_LABELS.get(fam, fam)}")
        L("")

        for r in rules:
            gate = RULE_GATES.get(r.id)
            gate_s = f"`{gate.kind}`" if gate else "—"
            if gate and gate.startup_delay_seconds:
                gate_s += f" (startup {gate.startup_delay_seconds:g}s)"

            L(f"### `{r.id}` — {r.title}")
            L("")
            L(f"**Equation:** {r.equation}")
            L("")
            L("| Field | Value |")
            L("| --- | --- |")
            L(f"| Family | `{r.family}` |")
            L(f"| Equipment kinds | {', '.join(f'`{k}`' for k in r.equipment_kinds)} |")
            L(f"| Operational gate | {gate_s} |")
            L(f"| Default confirm | {r.confirm_seconds:g}s |")
            flags = []
            if r.sensor_sweep:
                flags.append("sensor_sweep")
            if r.control_output_sweep:
                flags.append("control_output_sweep")
            L(f"| Sweep | {', '.join(f'`{f}`' for f in flags) if flags else '—'} |")
            L("")

            L("#### Points → Haystack tags (this chart)")
            L("")
            if r.sensor_sweep or r.control_output_sweep:
                L(
                    "Sweep rule: plots **sensors / control outputs present** on the equipment "
                    "(see sweep role lists in `cookbook_catalog.py`). No fixed required-role list."
                )
                L("")
            if r.required_roles or r.optional_roles:
                L("| Cookbook role | Haystack-like tag | Requirement |")
                L("| --- | --- | --- |")
                for role in r.required_roles:
                    L(role_row(role, "required"))
                for role in r.optional_roles or []:
                    if role not in r.required_roles:
                        L(role_row(role, "optional"))
                L("")
            elif not (r.sensor_sweep or r.control_output_sweep):
                L("_No fixed roles._")
                L("")

            L("#### Plot series")
            L("")
            plot_roles = list(r.required_roles) + [
                x for x in (r.optional_roles or []) if x not in r.required_roles
            ]
            if r.sensor_sweep:
                L("- Present sweep sensors (temps / statuses on mapped frame)")
            elif r.control_output_sweep:
                L("- Present 0–100% control outputs (dampers / valves / fan cmds)")
            elif plot_roles:
                for role in plot_roles:
                    L(f"- `{role}` → `{haystack(role)}`")
            else:
                L("- Chart falls back to common roles present (`sat`, `zone_t`, …) if any")
            L("- `confirmed_fault` swim lane (bool shade) when the rule was run")
            L("")

            L("#### Sliders (tune params)")
            L("")
            if r.params:
                L("| Key | Label | Unit | Default | Min | Max | Step |")
                L("| --- | --- | --- | ---: | ---: | ---: | ---: |")
                for p in r.params:
                    L(
                        f"| `{p.key}` | {p.label} | {p.unit} | {p.default:g} | "
                        f"{p.min:g} | {p.max:g} | {p.step:g} |"
                    )
            else:
                L("_No tune params_ (confirm may still appear via shared confirm slider).")
            L("")

            hint = ANALYTICS_HINTS.get(r.id)
            L("#### Analytics / related views")
            L("")
            if hint:
                L(hint)
            else:
                L(
                    "Fault hours / % on Results + FDD DOCX card; "
                    "RCx overlays only if roles match a preset."
                )
            L("")

    L("---")
    L("")
    L("## Appendix A — `COOKBOOK_TO_HAYSTACK_POINT` (canonical export)")
    L("")
    L("| Cookbook role | Haystack-like tag |")
    L("| --- | --- |")
    for role, tag in sorted(COOKBOOK_TO_HAYSTACK_POINT.items()):
        L(f"| `{role}` | `{tag}` |")

    L("")
    L("## Appendix B — Extended Haystack-style names used in this catalog")
    L("")
    L("These roles appear on rules but are **not** yet keys in `COOKBOOK_TO_HAYSTACK_POINT`.")
    L("Prefer adding them to the dict when you next touch mapping exports.")
    L("")
    L("| Cookbook role | Suggested Haystack-like tag |")
    L("| --- | --- |")
    for role, tag in sorted(EXTENDED_HS.items()):
        if role not in COOKBOOK_TO_HAYSTACK_POINT:
            L(f"| `{role}` | `{tag}` |")

    L("")
    L("## Appendix C — Related RCx presets (not the 50)")
    L("")
    L(
        "See [`RCX_PLOTS.md`](RCX_PLOTS.md). Reset scatters / duct-static box "
        "share roles with plant/AHU rules above."
    )
    L("")
    L("## Appendix D — Building-level analytics (not per-rule charts)")
    L("")
    L("| View | Where | Roles / inputs |")
    L("| --- | --- | --- |")
    L("| Motor weekly runtime | Overview / Analytics | fan/pump/compressor **status** preferred |")
    L(
        "| Mech-cooling OAT bins | Overview / Analytics | plant pump/status or DX compressor; "
        "**web OAT**; never CHW valve % |"
    )
    L("| Sensor fault summary | Plots (device) | sensors involved in FAULT SV-* |")
    L("| Occupancy calendar | Overview | writes `occ_mode` for SCHED-1 |")
    L("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(lines)} lines, {len(RULES)} rules)")


if __name__ == "__main__":
    main()
