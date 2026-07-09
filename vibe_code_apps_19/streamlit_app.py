"""Vibe Code App 19 — 50-rule pandas/Streamlit FDD demo."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.cache import (  # noqa: E402
    cached_building_tree,
    cached_duckdb,
    cached_parquet,
    cached_rule_defaults,
    cached_sqlite,
    cached_upload_bytes,
    cached_weather,
)
from app.charts import rule_result_chart  # noqa: E402
from app.config import AppConfig  # noqa: E402
from app.data_loader import discover_equipment, infer_poll_seconds, validate_dataframe  # noqa: E402
from app.mapping_wizard import (  # noqa: E402
    DEFAULT_BUILDING_ID,
    DEFAULT_SITE_ID,
    equipment_context,
    flat_role_map_from_sites,
    load_site_mapping,
    save_site_mapping,
    upsert_equipment_roles,
    wrap_flat_role_map,
)
from app.reports import debug_frame, html_report, markdown_report, results_summary_table, to_csv_bytes  # noqa: E402
from app.role_map import apply_role_map, enrich_role_map_from_equipment, load_role_map, roles_from_columns_csv, save_role_map, suggest_roles  # noqa: E402
from app.rules import CANONICAL_RULE_COUNT, RULES, RULES_BY_ID, run_all, run_rule  # noqa: E402
from app.rules.runner import infer_equipment_kind, run_batch  # noqa: E402
from app.site_model import Building, Site, equipment_type_from_id  # noqa: E402
from app.source_profile import load_uploaded_csvs, normalize_long_source, normalize_wide_source, profile_csv_source  # noqa: E402
from app.sql_sources import SqlServerConfig, load_sqlserver_query, sqlserver_available, validate_readonly_sql  # noqa: E402

st.set_page_config(page_title="Vibe19 FDD Demo", layout="wide")
st.title("Vibe Code App 19 — 50-rule pandas FDD lab")
st.caption(
    "Educational Streamlit demo with the full Open-FDD **pandas cookbook** (50 rules). "
    "Production Rust/DataFusion engine: [Open-FDD](https://github.com/bbartling/open-fdd)."
)


@st.cache_data
def load_inventory(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def _init_state() -> None:
    cfg = AppConfig.load()
    if "site_mapping" not in st.session_state:
        st.session_state.site_mapping = load_site_mapping(cfg.role_map_path)
    for k, v in {
        "equipment_frames": {},
        "selected_equipment": None,
        "batch_results": [],
        "params": {},
        "engineer_notes": {},
        "role_map": flat_role_map_from_sites(st.session_state.site_mapping),
        "weather": None,
        "building_id": cfg.building_id,
        "site_id": DEFAULT_SITE_ID,
        "data_root": str(cfg.data_root),
        "data_source": "BUILDING_100",
        "upload_profiles": {},
    }.items():
        st.session_state.setdefault(k, v)


def _sync_role_map_from_sites() -> None:
    st.session_state.role_map = flat_role_map_from_sites(st.session_state.site_mapping)


def _attach_frames_meta(frames: dict[str, pd.DataFrame]) -> None:
    rm = st.session_state.role_map
    for eq_id, df in frames.items():
        sid, bid, etype = equipment_context(st.session_state.site_mapping, eq_id)
        df.attrs.setdefault("site_id", sid)
        df.attrs.setdefault("building_id", bid)
        df.attrs.setdefault("equipment_type", etype)
        df.attrs["_role_map"] = rm


def _sidebar_sliders(defaults_cfg: dict) -> dict:
    out = dict(st.session_state.params)
    st.sidebar.subheader("Rule tuning")
    rule_filter = st.sidebar.text_input("Filter rules", "")
    for rule in RULES:
        if rule_filter and rule_filter.upper() not in rule.id:
            continue
        block = defaults_cfg.get(rule.id, {})
        if not block:
            continue
        with st.sidebar.expander(f"{rule.id} — {rule.title[:40]}", expanded=False):
            rp = dict(out.get(rule.id, {}))
            for pname, meta in block.items():
                rp[pname] = st.slider(
                    meta.get("label", pname),
                    min_value=float(meta["min"]),
                    max_value=float(meta["max"]),
                    value=float(rp.get(pname, meta["default"])),
                    step=float(meta.get("step", 0.5)),
                    help=meta.get("help", ""),
                    key=f"s_{rule.id}_{pname}",
                )
            out[rule.id] = rp
    if st.sidebar.button("Reset sliders"):
        st.session_state.params = {}
        st.rerun()
    st.session_state.params = out
    return out


def _load_multi_upload(site_id: str, building_id: str) -> dict[str, pd.DataFrame]:
    files = st.sidebar.file_uploader("CSV files", type=["csv"], accept_multiple_files=True)
    if not files:
        return {}
    frames: dict[str, pd.DataFrame] = {}
    profiles = {}
    for raw in load_uploaded_csvs(files):
        prof = profile_csv_source(raw.df, raw.name)
        profiles[raw.name] = prof
        default_eq = Path(raw.name).stem.replace(" ", "_").upper()
        eq = st.sidebar.text_input(f"Equipment ID ({raw.name})", default_eq, key=f"eq_{raw.name}")
        fmt = st.sidebar.selectbox(f"Format ({raw.name})", ["wide", "long"], key=f"fmt_{raw.name}")
        if fmt == "long":
            part = normalize_long_source(raw.df, site_id=site_id, building_id=building_id, source_name=raw.name)
        else:
            part = normalize_wide_source(raw.df, equipment_id=eq, site_id=site_id, building_id=building_id, source_name=raw.name)
        frames.update(part)
    st.session_state.upload_profiles = profiles
    return frames


def _load_data(cfg: AppConfig) -> None:
    mode = st.sidebar.radio(
        "Data input",
        [
            "BUILDING_100 tree",
            "Local CSV folder",
            "Upload CSV",
            "Multi CSV upload",
            "SQLite",
            "DuckDB SELECT",
            "SQL Server",
            "Parquet",
        ],
    )
    site_id = st.sidebar.text_input("Site ID", st.session_state.site_id, key="sidebar_site")
    building_id = st.sidebar.text_input("Building ID", st.session_state.building_id, key="sidebar_bldg")
    st.session_state.site_id = site_id
    st.session_state.building_id = building_id

    frames: dict[str, pd.DataFrame] = {}
    weather = None
    source = mode

    if mode == "BUILDING_100 tree":
        root = st.sidebar.text_input("HVAC_DATA_ROOT", st.session_state.data_root)
        building = st.sidebar.text_input("Building ID (tree)", st.session_state.building_id)
        st.session_state.data_root, st.session_state.building_id = root, building
        frames = cached_building_tree(root, building)
        for eq_id in frames:
            frames[eq_id].attrs.setdefault("site_id", site_id or DEFAULT_SITE_ID)
            frames[eq_id].attrs.setdefault("building_id", building)
        weather = cached_weather(root, cfg.weather_subdir)
        source = f"{root}/{building}"
    elif mode == "Local CSV folder":
        folder = st.sidebar.text_input("Folder", st.session_state.data_root)
        p = Path(folder)
        if p.is_dir():
            for eq in discover_equipment(p):
                from app.cache import cached_equipment_csv

                df = cached_equipment_csv(str(eq["history_path"]), str(eq["columns_path"]) if eq["columns_path"] else None)
                df.attrs["equipment_id"] = eq["equipment_id"]
                df.attrs["site_id"] = site_id
                df.attrs["building_id"] = building_id
                frames[eq["equipment_id"]] = df
            source = str(p)
    elif mode == "Upload CSV":
        up = st.sidebar.file_uploader("CSV", type=["csv"])
        eq = st.sidebar.text_input("Equipment ID", "UPLOAD_1")
        if up:
            df = cached_upload_bytes(up.name, up.getvalue())
            df.attrs["equipment_id"] = eq
            df.attrs["site_id"] = site_id
            df.attrs["building_id"] = building_id
            frames[eq] = df
            source = f"upload:{up.name}"
    elif mode == "Multi CSV upload":
        frames = _load_multi_upload(site_id, building_id)
        source = f"multi-upload:{len(frames)} files"
    elif mode == "SQLite":
        db, table = st.sidebar.text_input("SQLite path"), st.sidebar.text_input("Table", "history")
        if db and table:
            df = cached_sqlite(db, table)
            eq = st.sidebar.text_input("Equipment ID", "SQLITE_1", key="sqeq")
            df.attrs.update(equipment_id=eq, site_id=site_id, building_id=building_id)
            frames[eq] = df
            source = f"sqlite:{db}/{table}"
    elif mode == "DuckDB SELECT":
        db = st.sidebar.text_input("DuckDB path")
        query = st.sidebar.text_area("Query", "SELECT * FROM history LIMIT 1000")
        if db and query.strip().lower().startswith("select"):
            try:
                validate_readonly_sql(query)
                df = cached_duckdb(db, query)
                eq = st.sidebar.text_input("Equipment ID", "DUCK_1", key="deq")
                df.attrs.update(equipment_id=eq, site_id=site_id, building_id=building_id)
                frames[eq] = df
                source = f"duckdb:{db}"
            except ValueError as exc:
                st.sidebar.error(str(exc))
    elif mode == "SQL Server":
        if not sqlserver_available():
            st.sidebar.warning("Install optional deps: `pip install sqlalchemy pyodbc`")
        cfg_ss = SqlServerConfig(
            server=st.sidebar.text_input("Server", ""),
            database=st.sidebar.text_input("Database", ""),
            username=st.sidebar.text_input("Username", ""),
            password=st.sidebar.text_input("Password", type="password"),
            trusted_connection=st.sidebar.checkbox("Trusted connection", value=False),
        )
        query = st.sidebar.text_area("SELECT query", "SELECT TOP 1000 * FROM history")
        if sqlserver_available() and cfg_ss.server and cfg_ss.database and query:
            try:
                validate_readonly_sql(query)
                if st.sidebar.button("Run SQL Server query"):
                    df = load_sqlserver_query(cfg_ss, query)
                    eq = st.sidebar.text_input("Equipment ID", "MSSQL_1", key="mseq")
                    df.attrs.update(equipment_id=eq, site_id=site_id, building_id=building_id)
                    frames[eq] = df
                    source = f"sqlserver:{cfg_ss.server}/{cfg_ss.database}"
            except (ValueError, ImportError) as exc:
                st.sidebar.error(str(exc))
    elif mode == "Parquet":
        pq = st.sidebar.text_input("Parquet path")
        if pq:
            df = cached_parquet(pq)
            eq = st.sidebar.text_input("Equipment ID", "PQ_1", key="peq")
            df.attrs.update(equipment_id=eq, site_id=site_id, building_id=building_id)
            frames[eq] = df
            source = f"parquet:{pq}"

    if frames:
        st.session_state.equipment_frames = frames
        st.session_state.weather = weather
        st.session_state.data_source = source
        rm = dict(st.session_state.role_map)
        for eq_id, raw_df in frames.items():
            enrich_role_map_from_equipment(
                rm,
                eq_id,
                Path(raw_df.attrs["columns_path"]) if raw_df.attrs.get("columns_path") else None,
                list(raw_df.columns),
            )
            upsert_equipment_roles(
                st.session_state.site_mapping,
                site_id=str(raw_df.attrs.get("site_id", site_id)),
                building_id=str(raw_df.attrs.get("building_id", building_id)),
                equipment_id=eq_id,
                equipment_type=str(raw_df.attrs.get("equipment_type", equipment_type_from_id(eq_id))),
                roles=rm.get(eq_id, {}),
            )
        st.session_state.role_map = rm
        _sync_role_map_from_sites()
        _attach_frames_meta(frames)
        if st.session_state.selected_equipment not in frames:
            st.session_state.selected_equipment = sorted(frames)[0]

    for sec in ("Overview", "Trends", "Fault Results"):
        st.session_state.engineer_notes[sec] = st.sidebar.text_area(
            sec, st.session_state.engineer_notes.get(sec, ""), height=70, key=f"n_{sec}"
        )


def _site_mapping_tab(cfg: AppConfig, selected: str, raw_df: pd.DataFrame) -> None:
    st.subheader("Site / building / equipment mapping")
    sites = st.session_state.site_mapping
    site_ids = sorted(sites.keys()) or [DEFAULT_SITE_ID]
    sid = st.selectbox("Site", site_ids, key="map_site")
    site = sites.setdefault(sid, Site(site_id=sid, site_name=sid))
    bids = sorted(site.buildings.keys()) or [DEFAULT_BUILDING_ID]
    bid = st.selectbox("Building", bids, key="map_bldg")
    building = site.buildings.setdefault(bid, Building(building_id=bid, building_name=bid, site_id=sid))
    etype = st.selectbox("Equipment type", ["AHU", "VAV", "CHW_PLANT", "BOILER", "HP", "WEATHER", "METER", "UNKNOWN"], index=0, key="map_etype")
    st.write(f"Editing equipment **{selected}**")
    inferred = {**suggest_roles(raw_df), **roles_from_columns_csv(Path(raw_df.attrs.get("columns_path")) if raw_df.attrs.get("columns_path") else None)}
    edit = dict(st.session_state.role_map.get(selected, {}))
    for role in sorted(set(list(inferred.keys()) + list(edit.keys()) + ["zone_t", "sat", "sat_sp", "oa_t", "fan_cmd"])):
        opts = [""] + list(raw_df.columns)
        cur = edit.get(role, inferred.get(role, ""))
        edit[role] = st.selectbox(role, opts, index=opts.index(cur) if cur in opts else 0, key=f"sm_{selected}_{role}")
    edit = {k: v for k, v in edit.items() if v}
    st.session_state.role_map[selected] = edit
    upsert_equipment_roles(sites, site_id=sid, building_id=bid, equipment_id=selected, equipment_type=etype, roles=edit)
    _sync_role_map_from_sites()
    c1, c2, c3 = st.columns(3)
    if c1.button("Save flat YAML"):
        save_role_map(cfg.role_map_path, st.session_state.role_map, nested=False)
        st.success("Saved flat role_map.yaml")
    if c2.button("Save nested site YAML"):
        save_site_mapping(cfg.role_map_path, sites)
        st.success("Saved nested sites YAML")
    if c3.button("Export nested YAML download"):
        st.download_button("Download nested mapping", yaml.safe_dump({"sites": {s: st.session_state.site_mapping[s].to_dict() for s in st.session_state.site_mapping}}, sort_keys=False), "site_mapping.yaml")


def main() -> None:
    _init_state()
    cfg = AppConfig.load()
    defaults_cfg = cached_rule_defaults(str(cfg.rule_defaults_path))
    inventory = load_inventory(str(APP_ROOT / "configs" / "rule_inventory.yaml"))
    _load_data(cfg)
    _sidebar_sliders(defaults_cfg)

    frames = st.session_state.equipment_frames
    if not frames:
        st.info("Set HVAC_DATA_ROOT or choose another input mode.")
        return

    eq_ids = sorted(frames)
    selected = st.selectbox("Equipment", eq_ids, index=eq_ids.index(st.session_state.selected_equipment))
    st.session_state.selected_equipment = selected
    raw_df = frames[selected]
    mapped = apply_role_map(raw_df, selected, st.session_state.role_map)
    mapped.attrs.update(raw_df.attrs)
    mapped.attrs["equipment_id"] = selected
    poll = float(raw_df.attrs.get("poll_seconds") or infer_poll_seconds(raw_df))
    kind = infer_equipment_kind(selected)

    tabs = st.tabs(
        [
            "Overview",
            "Data Input",
            "Role Mapping",
            "Site Mapping",
            "Rule Inventory",
            "Rule Tuning",
            "Fault Results",
            "Trends / Debug",
            "Export",
        ]
    )

    with tabs[0]:
        st.subheader("Overview")
        if st.session_state.engineer_notes.get("Overview"):
            st.markdown(st.session_state.engineer_notes["Overview"])
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Equipment", len(frames))
        c2.metric("Canonical rules", CANONICAL_RULE_COUNT)
        c3.metric("Rows", len(raw_df))
        c4.metric("Poll (s)", f"{poll:.0f}")
        c5.metric("Kind", kind)
        c6.metric("Site", raw_df.attrs.get("site_id", ""))
        st.write(f"**Source:** `{st.session_state.data_source}` | **Building:** `{raw_df.attrs.get('building_id', '')}`")

    with tabs[1]:
        st.subheader("Data Input")
        st.write("Mode and paths are configured in the sidebar.")
        if st.session_state.upload_profiles:
            st.json({k: {"format": v.format, "rows": v.row_count, "issues": v.issues} for k, v in st.session_state.upload_profiles.items()})
        issues = validate_dataframe(raw_df)
        st.write("Validation:", issues or "OK")
        st.dataframe(raw_df.head(100), use_container_width=True)

    with tabs[2]:
        st.subheader("Role Mapping (equipment)")
        inferred = {**suggest_roles(raw_df), **roles_from_columns_csv(Path(raw_df.attrs.get("columns_path")) if raw_df.attrs.get("columns_path") else None)}
        edit = dict(st.session_state.role_map.get(selected, {}))
        for role in sorted(set(list(inferred.keys()) + list(edit.keys()) + ["zone_t", "sat", "sat_sp", "oa_t", "fan_cmd"])):
            opts = [""] + list(raw_df.columns)
            edit[role] = st.selectbox(role, opts, index=opts.index(edit.get(role, inferred.get(role, ""))) if edit.get(role, inferred.get(role, "")) in opts else 0, key=f"r_{selected}_{role}")
        edit = {k: v for k, v in edit.items() if v}
        st.session_state.role_map[selected] = edit
        if st.button("Save role map"):
            save_role_map(cfg.role_map_path, st.session_state.role_map)
            st.success("Saved")

    with tabs[3]:
        _site_mapping_tab(cfg, selected, raw_df)

    with tabs[4]:
        st.subheader("Rule Inventory")
        results = st.session_state.batch_results
        if results:
            df_sum = results_summary_table(results)
            st.metric("Implemented", CANONICAL_RULE_COUNT)
            st.metric("PASS", int((df_sum["status"] == "PASS").sum()))
            st.metric("FAULT", int((df_sum["status"] == "FAULT").sum()))
            st.metric("SKIPPED", int((df_sum["status"] == "SKIPPED_MISSING_ROLES").sum()))
            st.metric("N/A", int((df_sum["status"] == "NOT_APPLICABLE_EQUIPMENT_TYPE").sum()))
            st.metric("ERROR", int((df_sum["status"] == "ERROR").sum()))
        inv_rows = inventory.get("rules", [])
        st.dataframe(pd.DataFrame(inv_rows)[["rule_id", "family", "title", "required_roles", "implemented", "test_coverage"]], use_container_width=True, height=400)

    with tabs[5]:
        st.subheader("Rule Tuning")
        scope = st.radio("Batch scope", ["selected equipment", "all equipment", "building", "site"], horizontal=True)
        if st.button("Run all 50 rules", type="primary"):
            if scope == "selected equipment":
                st.session_state.batch_results = run_all(mapped, st.session_state.params, poll, st.session_state.weather)
            else:
                bf = st.session_state.building_id if scope == "building" else None
                sf = st.session_state.site_id if scope == "site" else None
                st.session_state.batch_results = run_batch(
                    frames,
                    params_by_rule=st.session_state.params,
                    weather=st.session_state.weather,
                    building_filter=bf,
                    site_filter=sf,
                )
            st.success(f"Ran {len(st.session_state.batch_results)} evaluations")

    with tabs[6]:
        st.subheader("Fault Results")
        results = st.session_state.batch_results
        if not results:
            st.info("Run rules from Rule Tuning tab.")
        else:
            summary = results_summary_table(results)
            st.dataframe(summary.sort_values(["status", "fault_hours"], ascending=[True, False]), use_container_width=True)
            faulted = summary[summary["status"] == "FAULT"].sort_values("fault_hours", ascending=False).head(20)
            if not faulted.empty:
                st.write("**Top faults**")
                st.dataframe(faulted, use_container_width=True)
            skipped = summary[summary["status"] == "SKIPPED_MISSING_ROLES"]
            if not skipped.empty:
                with st.expander(f"Skipped missing roles ({len(skipped)})"):
                    st.dataframe(skipped[["rule_id", "equipment_id", "missing_roles", "notes"]], use_container_width=True)

    with tabs[7]:
        st.subheader("Trends / Debug")
        rule_pick = st.selectbox("Rule", [r.id for r in RULES])
        if st.button("Run single rule for charts"):
            st.session_state.single = run_rule(rule_pick, mapped, st.session_state.params.get(rule_pick, {}), poll, st.session_state.weather)
        if hasattr(st.session_state, "single") and st.session_state.single:
            r = st.session_state.single
            st.write(r.notes)
            fig = rule_result_chart(mapped, r)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            if r.confirmed_fault is not None:
                st.line_chart(r.confirmed_fault.astype(int))

    with tabs[8]:
        st.subheader("Export")
        results = st.session_state.batch_results
        if results:
            summary = results_summary_table(results)
            st.download_button("Summary CSV", to_csv_bytes(summary), "fdd_summary.csv")
            md = markdown_report(
                building_id=st.session_state.building_id,
                data_source=st.session_state.data_source,
                results=results,
                engineer_notes=st.session_state.engineer_notes,
                params_snapshot={rid: p for rid, p in st.session_state.params.items()},
            )
            st.download_button("Markdown report", md.encode(), "report.md")
            st.download_button("HTML report", html_report(md).encode(), "report.html")


if __name__ == "__main__":
    main()
