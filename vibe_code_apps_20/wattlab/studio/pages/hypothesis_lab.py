"""Existing Building Hypothesis Lab Studio page."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import streamlit as st

from wattlab.studio.state import namespaced_key

NS = "hypothesis_lab"


def _key(name: str) -> str:
    return namespaced_key(NS, name)


def _persist_upload(upload: Any, directory: Path, name: str) -> str | None:
    if upload is None:
        return None
    path = directory / name
    path.write_bytes(upload.getvalue())
    return str(path)


def _seed_values(profile: dict[str, Any], bundle: Any, source: str) -> dict[str, Any]:
    if source == "Studio profile":
        return profile
    if source == "Loaded dump" and bundle is not None:
        return dict(getattr(bundle, "model_seed", {}) or {})
    return {}


def render(*, profile: dict[str, Any] | None = None, bundle: Any = None) -> None:
    """Render a bounded, Docker-free hypothesis-plan workflow."""

    st.header("Existing Building Hypothesis Lab")
    st.caption(
        "Explore sparse-input operating, ventilation, and capacity hypotheses. "
        "A dry run writes plans and evidence artifacts; it does not claim simulated savings."
    )

    sources = ["Manual sparse inputs", "Studio profile"]
    if bundle is not None:
        sources.append("Loaded dump")
    source = st.selectbox("Seed source", sources, key=_key("seed_source"))
    seed = _seed_values(profile or {}, bundle, source)

    c1, c2 = st.columns(2)
    building_type = c1.text_input(
        "Building type", value=str(seed.get("building_type") or "office"), key=_key("building_type")
    )
    city = c2.text_input("City", value=str(seed.get("city") or "madison"), key=_key("city"))
    c3, c4 = st.columns(2)
    area = c3.number_input(
        "Floor area (ft²)",
        min_value=1.0,
        value=float(
            seed.get("conditioned_floor_area_ft2")
            or seed.get("floor_area_ft2")
            or 50000.0
        ),
        key=_key("area"),
    )
    floors = c4.number_input(
        "Floors", min_value=1, value=int(seed.get("floors") or 3), step=1, key=_key("floors")
    )

    autosize = st.checkbox("Plan an autosized reference", value=True, key=_key("autosize"))
    factors_pct = st.multiselect(
        "Capacity factors (% of autosized reference)",
        [100, 90, 80, 70, 60, 50],
        default=[100, 90, 80, 70, 60, 50],
        key=_key("capacity_factors"),
    )

    st.subheader("Schedule and weather extensions")
    s1, s2 = st.columns(2)
    weekday_hours = s1.slider(
        "Occupied weekday hours", 4, 24, 10, key=_key("weekday_hours")
    )
    schedule_variants = s2.multiselect(
        "Schedule variants",
        ["weekday", "continuous"],
        default=["weekday", "continuous"],
        key=_key("schedules"),
    )
    weather_extensions = st.multiselect(
        "Weather checks",
        ["typical_vs_observed_degree_days", "hot_design_week", "cold_design_week"],
        default=["typical_vs_observed_degree_days"],
        key=_key("weather"),
    )
    oa_values = st.multiselect(
        "Outdoor-air scenarios",
        ["zero_oa", "half_design_oa", "design_oa"],
        default=["zero_oa", "half_design_oa", "design_oa"],
        key=_key("oa"),
    )
    max_scenarios = st.slider(
        "Maximum scenarios", 1, 100, 30, key=_key("max_scenarios")
    )

    u1, u2 = st.columns(2)
    monthly = u1.file_uploader(
        "Monthly bills (optional)", type=["csv", "json"], key=_key("monthly_upload")
    )
    interval = u2.file_uploader(
        "Interval data (optional)", type=["csv", "json"], key=_key("interval_upload")
    )

    if st.button(
        "Create dry-run hypothesis plan",
        key=_key("run_dry"),
        type="primary",
        width="stretch",
    ):
        try:
            from wattlab.existing_building.explore import run_explore_existing

            out = Path(tempfile.mkdtemp(prefix="wattlab-hypothesis-"))
            operating_hours = []
            if "weekday" in schedule_variants:
                operating_hours.append(
                    {"name": f"weekday_{weekday_hours}h", "weekday_hours": weekday_hours}
                )
            if "continuous" in schedule_variants:
                operating_hours.append(
                    {"name": "continuous", "strategy": "fan_avail_continuous"}
                )
            oa_map = {
                "zero_oa": 0.0,
                "half_design_oa": 0.5,
                "design_oa": 1.0,
            }
            config = {
                "building_type": building_type,
                "city": city,
                "floor_area_ft2": area,
                "floors": floors,
                "autosizing": {"enabled": autosize},
                "capacity": {"factors": [value / 100 for value in factors_pct]},
                "operating_hours": operating_hours,
                "ventilation": [
                    {"name": name, "oa_fraction": oa_map[name]} for name in oa_values
                ],
                "weather_extensions": weather_extensions,
                "search": {"max_scenarios": max_scenarios},
            }
            bills_path = _persist_upload(monthly, out, "uploaded_monthly_bills.csv")
            interval_path = _persist_upload(interval, out, "uploaded_interval_data.csv")
            if bills_path:
                config["monthly_bills_path"] = bills_path
            if interval_path:
                config["interval_data_path"] = interval_path
            result = run_explore_existing(config, dry_run=True, out_dir=out)
            result["dry_run"] = True
            st.session_state[_key("result")] = result
            st.success(f"Planned {result['scenarios']} scenarios without Docker.")
        except (ImportError, OSError, ValueError) as exc:
            st.info(f"Hypothesis planning is unavailable: {exc}")

    result = st.session_state.get(_key("result"))
    badge = result.get("badge") if result else "CONCEPTUAL_HYPOTHESIS"
    st.markdown(f"**Badge: `{badge}`**")
    if not result:
        return

    out_dir = Path(result["out_dir"])
    produced = [out_dir / name for name in result.get("artifacts", [])]
    produced = [path for path in produced if path.is_file()]
    if produced:
        st.subheader("Report and artifacts")
        selected = st.selectbox(
            "Artifact", [path.name for path in produced], key=_key("artifact")
        )
        path = out_dir / selected
        mime = "text/html" if path.suffix == ".html" else "application/json"
        st.download_button(
            f"Download {selected}",
            data=path.read_bytes(),
            file_name=selected,
            mime=mime,
            key=_key("download"),
            width="stretch",
        )
