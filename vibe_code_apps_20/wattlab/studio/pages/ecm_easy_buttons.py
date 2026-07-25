"""Catalog-driven ECM Easy Buttons Studio page."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from wattlab.ecm.catalog import ECMEntry, load_catalog
from wattlab.ecm.interactions import detect_incompatibilities
from wattlab.ecm.packages import PACKAGES, resolve_package
from wattlab.ecm.ranking import complexity_sort_key
from wattlab.studio.ecm_scenario import load_ecm_scenario, save_ecm_scenario
from wattlab.studio.state import namespaced_key

NS = "ecm_easy"
ProxyEstimator = Callable[[dict[str, Any], list[str]], dict[str, dict[str, float]]]


def _key(name: str) -> str:
    return namespaced_key(NS, name)


def _selected_entries(entries: list[ECMEntry], package_names: list[str]) -> list[str]:
    selected = [
        entry.ecm_id
        for entry in entries
        if st.session_state.get(_key(f"select.{entry.ecm_id}"), False)
    ]
    for package_name in package_names:
        selected.extend(resolve_package(package_name))
    return list(dict.fromkeys(selected))


def _scenario_path() -> Path | None:
    raw = st.session_state.get("studio_ecm_scenario_path")
    if raw:
        return Path(str(raw))
    return None


def _ensure_checkbox_defaults(entries: list[ECMEntry], selected_ids: list[str]) -> None:
    """Seed checkbox keys once from ecm_scenario.json (agent prefill)."""
    if st.session_state.get(_key("scenario_seeded")):
        return
    want = set(selected_ids)
    for entry in entries:
        k = _key(f"select.{entry.ecm_id}")
        if k not in st.session_state:
            st.session_state[k] = entry.ecm_id in want
    st.session_state[_key("scenario_seeded")] = True
    if selected_ids:
        st.session_state[_key("scenario_ids")] = list(selected_ids)


def render(
    *,
    profile: dict[str, Any] | None = None,
    proxy_estimator: ProxyEstimator | None = None,
) -> None:
    """Render catalog cards, packages, compatibility checks, and safe actions."""

    st.header("ECM Easy Buttons")
    st.caption(
        "Full catalog stays available as checkboxes — packages only **add** selections "
        "(they never remove prior ECMs). "
        "**esco-top15** = common HVAC ESCO set · **energy-recovery** = ERV / toilet ER · "
        "**deep-doas-heat-pump** = DOAS+HP mega what-if · **partial-g36** / **pneumatic-to-ddc** = prior controls packages. "
        "Agents write `reports/ecm_scenario.json`; Re-apply / open this page to pre-check."
    )
    try:
        entries = load_catalog().list()
    except (OSError, ValueError, ImportError) as exc:
        st.info(f"The ECM catalog is unavailable: {exc}")
        return

    scenario = load_ecm_scenario(_scenario_path())
    if scenario.get("sort_preference") == "implementation_complexity":
        entries = sorted(entries, key=complexity_sort_key)
    _ensure_checkbox_defaults(entries, list(scenario.get("selected_ecm_ids") or []))
    recs = scenario.get("recommendations") or []
    if recs:
        st.info(
            "Agent recommendations (unchecked suggestions): "
            + ", ".join(str(r) for r in recs[:12])
        )

    packages = st.multiselect(
        "Bulk-select packages",
        sorted(PACKAGES),
        key=_key("packages"),
        help=(
            "Packages include catalog dependencies automatically and stack additively. "
            "esco-top15 = common ESCO HVAC; energy-recovery = ERV; "
            "deep-doas-heat-pump = DOAS+heat-pump deep retrofit screening."
        ),
    )

    grouped: dict[str, list[ECMEntry]] = {}
    for entry in entries:
        group = (
            f"{entry.implementation_complexity.title()} complexity"
            if scenario.get("sort_preference") == "implementation_complexity"
            else entry.category
        )
        grouped.setdefault(group, []).append(entry)
    for group, group_entries in grouped.items():
        with st.expander(group, expanded=False):
            for entry in group_entries:
                with st.container(border=True):
                    left, right = st.columns([4, 1])
                    left.markdown(f"**{entry.display_name}**  \n{entry.description}")
                    right.checkbox(
                        "Select",
                        key=_key(f"select.{entry.ecm_id}"),
                    )
                    st.caption(
                        f"`{entry.ecm_id}` · status **{entry.status}** · "
                        f"category **{entry.category}** · complexity **{entry.implementation_complexity}** · "
                        f"confidence **{entry.confidence}** · "
                        f"proxy {'✓' if entry.proxy_calculator else '—'} · "
                        f"EnergyPlus {'✓' if entry.energyplus_patch else '—'}"
                    )

    selected = _selected_entries(entries, packages)
    issues = detect_incompatibilities(selected) if selected else []
    for issue in issues:
        st.warning(issue.note)

    a1, a2, a3, a4 = st.columns(4)
    if a1.button("Add to scenario", key=_key("add"), width="stretch"):
        st.session_state[_key("scenario_ids")] = selected
        if selected:
            st.success(f"Added {len(selected)} ECMs to the scenario.")
        else:
            st.info("Select an ECM or package first.")

    scenario_ids = st.session_state.get(_key("scenario_ids"), selected)
    if a2.button(
        "Save to ecm_scenario.json",
        key=_key("save_scenario"),
        width="stretch",
    ):
        path = save_ecm_scenario(
            {
                **scenario,
                "selected_ecm_ids": list(scenario_ids or selected),
                "measure_set": (profile or {}).get("measure_set") or scenario.get("measure_set"),
                "notes": scenario.get("notes") or "Saved from Studio Easy Buttons",
            },
            path=_scenario_path(),
        )
        st.success(f"Wrote `{path}`")

    if a3.button(
        "Calculate Proxy",
        key=_key("calculate_proxy"),
        width="stretch",
        disabled=not scenario_ids,
    ):
        if proxy_estimator is None:
            st.session_state[_key("proxy_results")] = {
                ecm_id: {
                    "savings_kwh": 0.0,
                    "savings_therms": 0.0,
                    "note": "No screening calculator is registered in this host.",
                }
                for ecm_id in scenario_ids
            }
        else:
            st.session_state[_key("proxy_results")] = proxy_estimator(
                profile or {}, scenario_ids
            )
        # Push into capital-plan / ROI session state so ECMs page can roll up.
        st.session_state["studio_measures"] = [{"measure_id": m} for m in scenario_ids]
        st.session_state["studio_proxies"] = dict(
            st.session_state.get(_key("proxy_results")) or {}
        )
        try:
            from wattlab.studio.ecm_roi import rows_to_cost_map, seed_roi_cost_rows

            area = float(
                (profile or {}).get("conditioned_floor_area_ft2")
                or (profile or {}).get("floor_area_ft2")
                or 50000.0
            )
            roi_rows = seed_roi_cost_rows(
                list(scenario_ids),
                floor_area_ft2=area,
                existing=st.session_state.get("studio_ecm_roi_models"),
            )
            st.session_state["studio_ecm_roi_rows"] = roi_rows
            st.session_state["studio_costs"] = rows_to_cost_map(roi_rows)
        except Exception as exc:
            st.caption(f"ROI cost seed skipped: {exc}")
        st.success(
            f"Proxies for {len(scenario_ids)} ECMs — scroll to Per-ECM ROI / capital plan."
        )

    blocked = [
        load_catalog().get(ecm_id)
        for ecm_id in scenario_ids
        if load_catalog().get(ecm_id).status in {"NEEDS_IMPLEMENTATION", "RESEARCH"}
    ]
    run_disabled = not scenario_ids or bool(blocked)
    a4.button(
        "Run EnergyPlus",
        key=_key("run_energyplus"),
        width="stretch",
        disabled=run_disabled,
        help=(
            "Disabled for NEEDS_IMPLEMENTATION or RESEARCH ECMs. "
            "Conceptual EnergyPlus proxies remain explicitly labeled and selectable."
        ),
    )
    if blocked:
        st.warning(
            "EnergyPlus is disabled because the scenario contains: "
            + ", ".join(f"{entry.ecm_id} ({entry.status})" for entry in blocked)
        )

    proxy_results = st.session_state.get(_key("proxy_results"))
    if proxy_results:
        rows = [{"ecm_id": ecm_id, **values} for ecm_id, values in proxy_results.items()]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
