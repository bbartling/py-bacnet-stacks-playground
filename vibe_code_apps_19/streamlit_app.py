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
    cached_building_folder,
    cached_rule_defaults,
    cached_weather,
)
from app.analytics import (  # noqa: E402
    dataset_time_span,
    mech_cooling_oat_bins,
    motor_run_hours_table,
    motor_run_hours_totals,
    sensor_fault_summary,
)
from app.charts import mech_cooling_oat_histogram, plotly_config, rule_result_chart  # noqa: E402
from app.config import AppConfig  # noqa: E402
from app.data_loader import infer_poll_seconds, list_building_candidates, validate_dataframe  # noqa: E402
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
from app.reports import results_summary_table, to_csv_bytes  # noqa: E402
import importlib  # noqa: E402
from app import column_map_json as _column_map_json_mod  # noqa: E402
from app import role_map as _role_map_mod  # noqa: E402

# Streamlit keeps stale modules in memory across edits; force reload.
_column_map_json_mod = importlib.reload(_column_map_json_mod)
FAMILY_ORDER = _column_map_json_mod.FAMILY_ORDER
LLM_COLUMN_MAP_PROMPT = _column_map_json_mod.LLM_COLUMN_MAP_PROMPT
build_column_map_from_equipment_frames = _column_map_json_mod.build_column_map_from_equipment_frames
build_llm_prompt_for_frames = _column_map_json_mod.build_llm_prompt_for_frames
column_map_to_role_map = _column_map_json_mod.column_map_to_role_map
family_label = _column_map_json_mod.family_label
load_column_map_json = _column_map_json_mod.load_column_map_json
merge_column_map_into_role_map = _column_map_json_mod.merge_column_map_into_role_map
natural_key = _column_map_json_mod.natural_key
normalize_column_map = _column_map_json_mod.normalize_column_map
save_column_map_json = _column_map_json_mod.save_column_map_json
to_haystack_document = _column_map_json_mod.to_haystack_document
validate_column_map_against_frames = _column_map_json_mod.validate_column_map_against_frames

_role_map_mod = importlib.reload(_role_map_mod)
apply_role_map = _role_map_mod.apply_role_map
enrich_role_map_from_equipment = _role_map_mod.enrich_role_map_from_equipment
load_role_map = _role_map_mod.load_role_map
roles_from_columns_csv = _role_map_mod.roles_from_columns_csv
save_role_map = _role_map_mod.save_role_map
suggest_roles = _role_map_mod.suggest_roles
from app.rules import CANONICAL_RULE_COUNT, RULES, RULES_BY_ID, run_rule  # noqa: E402
from app.rules.operational_gate import RULE_GATES  # noqa: E402
from app.rules.runner import infer_equipment_kind  # noqa: E402
from app.site_model import Building, Site, equipment_type_from_id  # noqa: E402

try:
    from shared.branding import APP_TITLE
except ImportError:  # pragma: no cover
    APP_TITLE = "Open FDD Vibe Coder"

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption(
    "Educational Streamlit lab for the Open-FDD **pandas cookbook** (50 rules). "
    "Browse any local **building folder** — an LLM (or heuristic) builds a **JSON column→role map**, "
    "it does **not** rewrite your CSVs. "
    "Production Rust/DataFusion product: [Open-FDD](https://github.com/bbartling/open-fdd)."
)


@st.cache_data
def load_inventory(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def _init_state() -> None:
    cfg = AppConfig.load()
    if "site_mapping" not in st.session_state:
        st.session_state.site_mapping = load_site_mapping(cfg.role_map_path)
    demo_building = cfg.data_root / cfg.building_id
    default_folder = str(demo_building) if demo_building.is_dir() else str(cfg.data_root)
    for k, v in {
        "equipment_frames": {},
        "selected_equipment": None,
        "batch_results": [],
        "params": {},
        "engineer_notes": {},
        "role_map": flat_role_map_from_sites(st.session_state.site_mapping),
        "weather": None,
        "building_id": "",
        "site_id": DEFAULT_SITE_ID,
        "building_folder": default_folder,
        "data_root": str(cfg.data_root),
        "data_source": "",
        "column_map": {},
        "column_map_path": "",
        "require_operational_gates": True,
    }.items():
        st.session_state.setdefault(k, v)


def _sync_role_map_from_sites() -> None:
    st.session_state.role_map = flat_role_map_from_sites(st.session_state.site_mapping)


def _apply_column_map_json(data: dict) -> None:
    """Merge JSON column map into session role_map + site mapping."""
    normalized = normalize_column_map(data)
    st.session_state.column_map = normalized
    st.session_state.role_map = merge_column_map_into_role_map(
        st.session_state.role_map, normalized, prefer_json=True
    )
    for eq_id, roles in column_map_to_role_map(normalized).items():
        upsert_equipment_roles(
            st.session_state.site_mapping,
            site_id=st.session_state.site_id,
            building_id=st.session_state.building_id,
            equipment_id=eq_id,
            equipment_type=equipment_type_from_id(eq_id),
            roles=roles,
        )
    _sync_role_map_from_sites()
    if st.session_state.equipment_frames:
        _attach_frames_meta(st.session_state.equipment_frames)


def _rules_by_family() -> dict[str, list]:
    buckets: dict[str, list] = {f: [] for f in FAMILY_ORDER}
    for rule in RULES:
        fam = rule.family if rule.family in buckets else "other"
        buckets[fam].append(rule)
    for fam in buckets:
        buckets[fam].sort(key=lambda r: natural_key(r.id))
    return buckets


def _results_by_family(summary: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if summary.empty:
        return {}
    out: dict[str, pd.DataFrame] = {}
    fam_lookup = {r.id: r.family for r in RULES}
    df = summary.copy()
    df["family"] = df["rule_id"].map(lambda rid: fam_lookup.get(rid, "other"))
    for fam in FAMILY_ORDER:
        part = df[df["family"] == fam].copy()
        if part.empty:
            continue
        part = part.loc[
            sorted(
                part.index,
                key=lambda i: (natural_key(str(part.at[i, "rule_id"])), str(part.at[i, "equipment_id"])),
            )
        ]
        out[fam] = part
    return out


def _attach_frames_meta(frames: dict[str, pd.DataFrame]) -> None:
    rm = st.session_state.role_map
    for eq_id, df in frames.items():
        sid, bid, etype = equipment_context(st.session_state.site_mapping, eq_id)
        df.attrs.setdefault("site_id", sid)
        df.attrs.setdefault("building_id", bid)
        df.attrs.setdefault("equipment_type", etype)
        df.attrs["_role_map"] = rm


_CONFIRM_META = {
    "label": "Fault confirm delay",
    "default": 0.0,
    "min": 0.0,
    "max": 60.0,
    "step": 5.0,
    "unit": "min",
    "help": "Minutes a raw fault must persist before it is confirmed. 0 = confirm on first sample.",
}


@st.fragment
def _sidebar_sliders(defaults_cfg: dict) -> None:
    """Left-rail rule tuning. Fragment-isolated so slider moves do not re-run rules/plots."""
    out = dict(st.session_state.params)
    st.sidebar.subheader("Rule tuning")
    st.sidebar.caption(
        "Sliders only change thresholds. Rules update when you click **Run** (Run Rules tab) or **Rerun cat.**"
    )
    st.session_state.require_operational_gates = st.sidebar.checkbox(
        "Require operational proof (fan/pump status)",
        value=st.session_state.get("require_operational_gates", True),
        help=(
            "When checked, RUN rules only evaluate while fan/pump/compressor is proven on "
            "(status preferred over command). Off-period samples become SKIPPED_EQUIPMENT_OFF, not PASS."
        ),
        key="ops_gate_global",
    )
    rule_filter = st.sidebar.text_input("Filter rules", "", key="tune_filter")
    fam_labels = [family_label(f) for f in FAMILY_ORDER if _rules_by_family().get(f)]
    fam_pick = st.sidebar.selectbox(
        "Category",
        ["(all)"] + fam_labels,
        key="tune_fam",
    )
    fam_lookup = {family_label(f): f for f in FAMILY_ORDER}
    allow_ids = None
    fam_key = None
    if fam_pick != "(all)":
        fam_key = fam_lookup[fam_pick]
        allow_ids = {r.id for r in _rules_by_family().get(fam_key, [])}

    for rule in RULES:
        if allow_ids is not None and rule.id not in allow_ids:
            continue
        if rule_filter and rule_filter.upper() not in rule.id:
            continue
        block = dict(defaults_cfg.get(rule.id, {}))
        if "confirm_min" not in block:
            block["confirm_min"] = dict(_CONFIRM_META)
        gate = RULE_GATES.get(rule.id)
        if gate and gate.kind != "always":
            block.setdefault(
                "require_operational_gate",
                {
                    "label": "Require operational proof",
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 1.0,
                    "unit": "0/1",
                    "help": "1 = gate on for this rule (fan/pump proven). 0 = evaluate all samples.",
                },
            )
            block.setdefault(
                "startup_delay_min",
                {
                    "label": "Startup delay",
                    "default": gate.startup_delay_seconds / 60.0,
                    "min": 0.0,
                    "max": 30.0,
                    "step": 1.0,
                    "unit": "min",
                    "help": "Ignore samples until equipment has been proven on this long.",
                },
            )
        with st.sidebar.expander(f"{rule.id} — {rule.title[:36]}", expanded=False):
            rp = dict(out.get(rule.id, {}))
            # Fault confirm delay first, then gate toggles, then other params
            preferred = ["confirm_min", "require_operational_gate", "startup_delay_min"]
            ordered = [k for k in preferred if k in block] + [k for k in block if k not in preferred]
            for pname in ordered:
                meta = block[pname]
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

    c1, c2 = st.sidebar.columns(2)
    if c1.button("Reset", key="reset_tune"):
        st.session_state.params = {}
        st.rerun()
    st.session_state.params = out
    st.session_state["_sidebar_fam_key"] = fam_key
    if c2.button("Rerun cat.", key="rerun_cat_sidebar", help="Rerun the selected mechanical category on all equipment"):
        st.session_state["_pending_rerun_family"] = fam_key  # None = all
        st.rerun()


def _units_map() -> dict[str, str]:
    cm = st.session_state.get("column_map") or {}
    units = cm.get("units") if isinstance(cm, dict) else None
    return dict(units) if isinstance(units, dict) else {}


def _equip_by_type(frames: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for eq_id, df in frames.items():
        et = str(df.attrs.get("equipment_type") or equipment_type_from_id(eq_id))
        buckets.setdefault(et, []).append(eq_id)
    return {k: sorted(v, key=natural_key) for k, v in sorted(buckets.items())}


def _mapped_equipment(eq_id: str, frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, float]:
    raw = frames[eq_id]
    mapped = apply_role_map(raw, eq_id, st.session_state.role_map)
    mapped.attrs.update({k: v for k, v in raw.attrs.items() if not isinstance(v, Path)})
    mapped.attrs["equipment_id"] = eq_id
    if raw.attrs.get("columns_path") is not None:
        mapped.attrs["columns_path"] = str(raw.attrs["columns_path"])
    poll = float(raw.attrs.get("poll_seconds") or infer_poll_seconds(raw))
    return mapped, poll


def _run_rule_list(
    eq_ids: list[str],
    rules: list,
    frames: dict[str, pd.DataFrame],
) -> list:
    results = []
    gate_on = bool(st.session_state.get("require_operational_gates", True))
    for eq_id in eq_ids:
        mapped, poll = _mapped_equipment(eq_id, frames)
        for rule in rules:
            results.append(
                run_rule(
                    rule.id,
                    mapped,
                    st.session_state.params.get(rule.id, {}),
                    poll,
                    st.session_state.weather,
                    require_operational_gates=gate_on,
                )
            )
    return results


def _result_lookup(results: list) -> dict[tuple[str, str], object]:
    return {(r.equipment_id, r.rule_id): r for r in results}


def _pick_local_folder() -> str | None:
    """Native OS folder dialog (local Streamlit only). Returns None if cancelled/unavailable."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        chosen = filedialog.askdirectory(title="Select building folder (or parent of buildings)")
        root.destroy()
        return chosen or None
    except Exception:
        return None


def _materialize_uploaded_tree(files: list) -> Path | None:
    """Write a browser-picked directory upload into a temp tree and return its root."""
    import tempfile

    if not files:
        return None
    tmp = Path(tempfile.mkdtemp(prefix="vibe19_building_"))
    for f in files:
        rel = getattr(f, "name", None) or "file.csv"
        # Streamlit directory uploads use forward-slash relative paths.
        dest = tmp / Path(*Path(str(rel).replace("\\", "/")).parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(f.getvalue())
    candidates = list_building_candidates(tmp)
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        # Multiple buildings under one upload — prefer deepest common parent already tmp
        return tmp
    return tmp if any(tmp.rglob("history_wide.csv")) else None


def _commit_frames(
    frames: dict[str, pd.DataFrame],
    *,
    site_id: str,
    building_id: str,
    source: str,
    weather,
) -> None:
    if not frames:
        return
    st.session_state.equipment_frames = frames
    st.session_state.weather = weather
    st.session_state.data_source = source
    st.session_state.building_id = building_id
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


def _load_data(cfg: AppConfig) -> None:
    """Minimal load: Browse folder or paste path. No Site ID / notes / upload clutter."""
    st.sidebar.markdown("**Building data**")
    if st.sidebar.button("Browse folder…", help="Pick a building folder on this PC"):
        picked = _pick_local_folder()
        if picked:
            st.session_state.building_folder = picked
            st.rerun()

    folder_text = st.sidebar.text_input(
        "Folder path",
        help="Building folder (AHU_*/VAV_*/… with history_wide.csv), or parent of several buildings.",
        key="building_folder",
    )

    frames: dict[str, pd.DataFrame] = {}
    weather = None
    building_id = ""
    source = ""
    site_id = st.session_state.site_id or DEFAULT_SITE_ID

    path = Path(folder_text).expanduser() if folder_text else None
    if path and path.is_dir():
        candidates = list_building_candidates(path)
        if not candidates:
            st.sidebar.warning("No `history_wide.csv` under that path.")
        else:
            labels = [c.name for c in candidates]
            if len(candidates) == 1 and candidates[0].resolve() == path.resolve():
                chosen = candidates[0]
            else:
                pick = st.sidebar.selectbox("Building", labels, index=0)
                chosen = next(c for c in candidates if c.name == pick)
            building_id = chosen.name
            st.session_state.data_root = str(chosen.parent)
            try:
                frames = cached_building_folder(str(chosen.resolve()))
            except Exception as exc:  # pragma: no cover
                st.sidebar.error(str(exc))
                frames = {}
            for eq_id in frames:
                frames[eq_id].attrs.setdefault("site_id", site_id)
                frames[eq_id].attrs.setdefault("building_id", building_id)
                # Avoid Streamlit Arrow warning on Path attrs
                if frames[eq_id].attrs.get("columns_path") is not None:
                    frames[eq_id].attrs["columns_path"] = str(frames[eq_id].attrs["columns_path"])
            weather = cached_weather(str(chosen.parent), cfg.weather_subdir)
            source = str(chosen.resolve())
            if frames:
                st.sidebar.caption(f"{len(frames)} equip · `{building_id}`")
    elif folder_text:
        st.sidebar.warning("Path not found — use Browse folder…")

    _commit_frames(frames, site_id=site_id, building_id=building_id, source=source, weather=weather)


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
    _load_data(cfg)
    _sidebar_sliders(defaults_cfg)

    frames = st.session_state.equipment_frames
    if not frames:
        st.info(
            "Sidebar → **Browse folder…** (or paste a building folder path), then map columns and run rules. "
            "Use left-rail **Rule tuning** sliders, then **Run** on the Run Rules tab, then browse **Plots** by device."
        )
        return

    # Sidebar "Rerun cat." — apply after frames exist
    pending = st.session_state.pop("_pending_rerun_family", "__none__")
    if pending != "__none__":
        rules = RULES if pending is None else _rules_by_family().get(pending, [])
        st.session_state.batch_results = _run_rule_list(sorted(frames), rules, frames)
        label = "all rules" if pending is None else family_label(pending)
        st.toast(f"Reran {label}: {len(st.session_state.batch_results)} evaluations")

    eq_ids = sorted(frames, key=natural_key)
    selected = st.selectbox("Equipment", eq_ids, index=eq_ids.index(st.session_state.selected_equipment) if st.session_state.selected_equipment in eq_ids else 0)
    st.session_state.selected_equipment = selected
    mapped, poll = _mapped_equipment(selected, frames)
    kind = infer_equipment_kind(selected)
    units_map = _units_map()
    by_type = _equip_by_type(frames)

    tabs = st.tabs(
        [
            "Overview",
            "Data & Mapping",
            "Run Rules",
            "Results by Category",
            "Plots",
            "Analytics",
            "Export",
        ]
    )

    span = dataset_time_span(frames)
    motor_tbl = motor_run_hours_table(frames, st.session_state.role_map)
    motor_tot = motor_run_hours_totals(motor_tbl)
    cool_bins = mech_cooling_oat_bins(
        frames,
        st.session_state.role_map,
        weather=st.session_state.weather,
    )
    start_s = span["start"].strftime("%Y-%m-%d %H:%M") if span["start"] is not None else "—"
    end_s = span["end"].strftime("%Y-%m-%d %H:%M") if span["end"] is not None else "—"

    with tabs[0]:
        st.subheader("Overview")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Equipment", len(frames))
        c2.metric("Rules", CANONICAL_RULE_COUNT)
        c3.metric("Rows (selected)", len(mapped))
        c4.metric("Poll (s)", f"{poll:.0f}")
        c5.metric("Kind", kind)
        st.caption(f"`{st.session_state.data_source}`")

        d1, d2, d3 = st.columns(3)
        d1.metric("Dataset start", start_s)
        d2.metric("Dataset end", end_s)
        d3.metric("Span (h)", f"{span['span_hours']:.1f}")

        m1, m2, m3 = st.columns(3)
        m1.metric("Fan / motor run hours", f"{motor_tot['fan_hours']:.1f}")
        m2.metric("Pump run hours", f"{motor_tot['pump_hours']:.1f}")
        m3.metric("Total motor hours", f"{motor_tot['total_hours']:.1f}")
        st.caption(
            "Totals prefer **fan_status** over fan_cmd when both exist. "
            "Per-motor breakdown below loops every mapped fan/pump signal."
        )
        st.markdown("##### Per-motor run hours")
        if motor_tbl.empty:
            st.info("No fan_cmd / fan_status / pump signals mapped yet.")
        else:
            st.dataframe(motor_tbl, hide_index=True, width="stretch", height=min(420, 80 + 28 * len(motor_tbl)))

        st.markdown("##### Mechanical cooling vs OAT (chiller + DX only)")
        st.caption(
            "Hours when a **chiller** (compressor/pump proof) or **AHU DX compressor** is on, "
            "binned by outdoor-air temperature. Hydronic cool-valve-only AHUs are excluded."
        )
        cool_fig = mech_cooling_oat_histogram(cool_bins)
        if cool_fig is None:
            st.info(
                "No chiller / DX compressor run signals found. Map `compressor_status`, "
                "`dx_cool_cmd`, or CHW pump/enable roles to populate this histogram."
            )
        else:
            st.plotly_chart(cool_fig, width="stretch", config=plotly_config(filename="mech_cooling_oat_bins"))
            with st.expander("Mech cooling bin table"):
                st.dataframe(cool_bins, hide_index=True, width="stretch")

        st.markdown(
            "Tune thresholds in the **left sidebar** → **Run Rules** (all or by category) "
            "or sidebar **Rerun cat.** → browse **Plots** by device type (AHU / VAV / plant…)."
        )
        st.markdown("**Devices by type**")
        type_counts = pd.DataFrame(
            [{"type": t, "count": len(ids)} for t, ids in by_type.items()]
        )
        st.dataframe(type_counts, hide_index=True, width="stretch")

    with tabs[1]:
        st.subheader("Data & column → role mapping")
        st.write(
            "Map historian columns with Haystack-like `points` (or Auto-build). "
            "Units in the JSON keep plots from mixing families."
        )
        raw_df = frames[selected]
        map_cols = st.columns(2)
        with map_cols[0]:
            st.markdown("##### JSON column map (LLM / heuristic)")
            bid = st.session_state.building_id or "building"
            default_json = APP_ROOT / "configs" / f"{bid.lower()}_column_map.json"
            if not default_json.is_file():
                demo = APP_ROOT / "configs" / "building_100_column_map.json"
                default_json = demo if demo.is_file() and bid.upper() == "BUILDING_100" else default_json
            json_path = st.text_input(
                "JSON map path (optional)",
                st.session_state.column_map_path or (str(default_json) if default_json.is_file() else ""),
            )
            uploaded_json = st.file_uploader("Or upload column map JSON", type=["json"], key="colmap_upload")
            if st.button("Load JSON map from path") and json_path:
                try:
                    data = load_column_map_json(json_path)
                    _apply_column_map_json(data)
                    st.session_state.column_map_path = json_path
                    st.success(f"Loaded map for {len(data.get('equipment', {}))} equipment")
                except Exception as exc:
                    st.error(str(exc))
            if uploaded_json is not None and st.button("Apply uploaded JSON map"):
                try:
                    import json as _json

                    data = normalize_column_map(_json.loads(uploaded_json.getvalue().decode("utf-8")))
                    _apply_column_map_json(data)
                    st.success(f"Applied uploaded map ({len(data.get('equipment', {}))} equipment)")
                except Exception as exc:
                    st.error(str(exc))
            if st.button("Auto-build JSON map from loaded CSVs"):
                data = build_column_map_from_equipment_frames(
                    frames,
                    building_id=st.session_state.building_id,
                    site_ref=st.session_state.site_id,
                    generated_by="heuristic",
                )
                _apply_column_map_json(data)
                out_name = f"{(st.session_state.building_id or 'building').lower()}_column_map.json"
                out = APP_ROOT / "configs" / out_name
                save_column_map_json(out, data, haystack=True)
                st.session_state.column_map_path = str(out)
                issues = validate_column_map_against_frames(data, frames)
                st.success(f"Built & saved Haystack map `{out.name}` ({len(data['equipment'])} equip)")
                if issues:
                    st.warning("\n".join(issues[:15]))

        with map_cols[1]:
            st.markdown("##### LLM workflow (Haystack points → cookbook roles)")
            filled_prompt = build_llm_prompt_for_frames(
                frames,
                building_id=st.session_state.building_id,
                site_ref=st.session_state.site_id,
            )
            with st.expander("Filled LLM prompt", expanded=False):
                st.code(filled_prompt, language="text")
            st.download_button(
                "Download LLM prompt as .txt",
                data=filled_prompt.encode("utf-8"),
                file_name=f"{(st.session_state.building_id or 'building').lower()}_llm_column_map_prompt.txt",
                mime="text/plain",
                key="dl_llm_prompt",
            )
            if st.session_state.column_map:
                st.download_button(
                    "Download Haystack column map JSON",
                    data=__import__("json").dumps(
                        to_haystack_document(st.session_state.column_map), indent=2
                    ).encode(),
                    file_name="column_map.json",
                    mime="application/json",
                    key="dl_colmap_mapping_tab",
                )

        st.divider()
        st.markdown("##### Per-equipment role editor")
        st.caption(
            "Optional manual override per CSV / device. Skip this if the LLM (or Auto-build) JSON map "
            "already assigned the right columns — only use these dropdowns to fix gaps or mistakes."
        )
        inferred = {
            **suggest_roles(raw_df),
            **roles_from_columns_csv(Path(raw_df.attrs.get("columns_path")) if raw_df.attrs.get("columns_path") else None),
        }
        edit = dict(st.session_state.role_map.get(selected, {}))
        for role in sorted(set(list(inferred.keys()) + list(edit.keys()) + ["zone_t", "sat", "sat_sp", "oa_t", "fan_cmd"])):
            opts = [""] + list(raw_df.columns)
            cur = edit.get(role, inferred.get(role, ""))
            edit[role] = st.selectbox(
                role,
                opts,
                index=opts.index(cur) if cur in opts else 0,
                key=f"r_{selected}_{role}",
            )
        edit = {k: v for k, v in edit.items() if v}
        st.session_state.role_map[selected] = edit
        if st.button("Save role map YAML"):
            save_role_map(cfg.role_map_path, st.session_state.role_map)
            st.success("Saved role_map.yaml")
        with st.expander("Site / building nesting"):
            _site_mapping_tab(cfg, selected, raw_df)
        st.divider()
        st.markdown("##### Raw data preview")
        issues = validate_dataframe(raw_df)
        st.write("Validation:", issues or "OK")
        st.dataframe(raw_df.head(100), width="stretch")

    with tabs[2]:
        st.subheader("Run rules")
        st.caption(
            "Sidebar sliders only store thresholds — they do **not** re-evaluate rules. "
            "Click **Run** here (or sidebar **Rerun cat.**) after tuning."
        )
        scope = st.radio(
            "Equipment scope",
            ["selected equipment", "all equipment"],
            horizontal=True,
            key="run_scope",
        )
        mode = st.radio(
            "Rule set",
            ["All 50 rules", "One mechanical category"],
            horizontal=True,
            key="run_mode",
        )
        fam_key = None
        if mode == "One mechanical category":
            labels = [family_label(f) for f in FAMILY_ORDER if _rules_by_family().get(f)]
            pick = st.selectbox("Category", labels, key="run_fam_label")
            fam_key = {family_label(f): f for f in FAMILY_ORDER}[pick]

        if st.button("Run", type="primary", key="run_btn"):
            target_rules = RULES if fam_key is None else _rules_by_family().get(fam_key, [])
            eq_list = [selected] if scope == "selected equipment" else sorted(frames, key=natural_key)
            st.session_state.batch_results = _run_rule_list(eq_list, target_rules, frames)
            st.success(f"Ran {len(st.session_state.batch_results)} evaluations — open **Plots** or **Analytics**.")

    with tabs[3]:
        st.subheader("Results by mechanical category")
        results = st.session_state.batch_results
        if not results:
            st.info("Run rules (main tab or sidebar **Rerun cat.**), then review here or on **Plots**.")
        else:
            summary = results_summary_table(results)
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("PASS", int((summary["status"] == "PASS").sum()))
            m2.metric("FAULT", int((summary["status"] == "FAULT").sum()))
            m3.metric("SKIPPED", int((summary["status"] == "SKIPPED_MISSING_ROLES").sum()))
            m4.metric("EQUIP OFF", int((summary["status"] == "SKIPPED_EQUIPMENT_OFF").sum()))
            m5.metric("N/A", int((summary["status"] == "NOT_APPLICABLE_EQUIPMENT_TYPE").sum()))
            m6.metric("ERROR", int((summary["status"] == "ERROR").sum()))
            by_fam = _results_by_family(summary)
            fam_tabs = st.tabs([family_label(f) for f in by_fam])
            for tab, (fam, part) in zip(fam_tabs, by_fam.items()):
                with tab:
                    st.dataframe(part, width="stretch", height=420)
                    faults = part[part["status"] == "FAULT"]
                    if not faults.empty:
                        st.write("**Faults**")
                        st.dataframe(faults.sort_values("fault_hours", ascending=False), width="stretch")

    with tabs[4]:
        st.subheader("Plots by device")
        st.caption(
            "Pick a mechanical type → device (each AHU / VAV / plant unit has its own plots). "
            "Each rule is one figure: rainbow-colored signals on unique unit axes, "
            "confirmed fault as a shaded swim lane. Camera icon → PNG/JPEG."
        )
        plot_fmt = st.selectbox("Download format", ["png", "jpeg", "svg", "webp"], index=0, key="plot_fmt")
        show_pass = st.checkbox("Show PASS plots (not only FAULT)", value=False, key="plot_show_pass")
        type_opts = list(by_type.keys()) or ["UNKNOWN"]
        cur_type = str(frames[selected].attrs.get("equipment_type") or equipment_type_from_id(selected))
        type_idx = type_opts.index(cur_type) if cur_type in type_opts else 0
        eq_type = st.selectbox("Device type", type_opts, index=type_idx, key="plot_eq_type")
        device_ids = by_type.get(eq_type, [])
        if not device_ids:
            st.warning("No devices of that type.")
        else:
            dev_idx = device_ids.index(selected) if selected in device_ids else 0
            device = st.selectbox("Device", device_ids, index=dev_idx, key="plot_device")
            st.session_state.selected_equipment = device
            plot_df, _ = _mapped_equipment(device, frames)
            eq_kind = infer_equipment_kind(device)

            applicable = [r for r in RULES if eq_kind in r.equipment_kinds or eq_kind == "unknown"]
            by_fam_rules: dict[str, list] = {f: [] for f in FAMILY_ORDER}
            for rule in applicable:
                fam = rule.family if rule.family in by_fam_rules else "other"
                by_fam_rules[fam].append(rule)

            lookup = _result_lookup(st.session_state.batch_results)
            if st.button("Run all applicable rules for this device", type="primary", key="plot_run_device"):
                new_res = _run_rule_list([device], applicable, frames)
                keep = [r for r in st.session_state.batch_results if r.equipment_id != device]
                st.session_state.batch_results = keep + new_res
                lookup = _result_lookup(st.session_state.batch_results)
                st.success(f"Evaluated {len(new_res)} rules on `{device}`")

            if not any(eq == device for eq, _rid in lookup):
                st.info("Click **Run all applicable rules for this device** (or sidebar **Rerun cat.**) to populate plots.")

            # Sensor fault summary statistics (SV-* FAULT results)
            device_results = [r for r in st.session_state.batch_results if r.equipment_id == device]
            sens = sensor_fault_summary(plot_df, device_results, equipment_id=device)
            if not sens.empty:
                st.markdown("##### Sensor fault summary statistics")
                st.caption("Mean/std/min/p50/max for sensors involved in FAULT sensor-validation rules — useful for engineer review and CSV export.")
                st.dataframe(sens, width="stretch", height=220)
                st.download_button(
                    "Download sensor fault stats CSV",
                    to_csv_bytes(sens),
                    f"{device}_sensor_fault_stats.csv",
                    key=f"dl_sens_{device}",
                )

            shown = 0
            for fam in FAMILY_ORDER:
                rules = by_fam_rules.get(fam) or []
                if not rules:
                    continue
                with st.expander(
                    f"{family_label(fam)} · {len(rules)} rules for {eq_type}",
                    expanded=(fam in {"ahu", "vav", "control"} and eq_type in {"AHU", "VAV"}),
                ):
                    for rule in rules:
                        r = lookup.get((device, rule.id))
                        if r is None:
                            st.caption(f"{rule.id} — {rule.title} · not run yet")
                            continue
                        if r.status in {"SKIPPED_MISSING_ROLES", "NOT_APPLICABLE_EQUIPMENT_TYPE", "ERROR", "SKIPPED_EQUIPMENT_OFF"}:
                            with st.container(border=True):
                                st.markdown(f"**{rule.id}** — {rule.title}")
                                st.caption(f"`{r.status}` · {rule.equation}")
                                if r.missing_roles:
                                    st.caption("Missing: " + ", ".join(r.missing_roles))
                            continue
                        if r.status == "PASS" and not show_pass:
                            continue
                        with st.container(border=True):
                            st.markdown(f"**{rule.id}** — {rule.title}")
                            fh = r.fault_hours if r.fault_hours is not None else 0.0
                            st.caption(f"`{r.status}` · fault hours: {fh:.2f}")
                            st.caption(rule.equation)
                            fig = rule_result_chart(
                                plot_df,
                                r,
                                required_roles=rule.required_roles,
                                units_map=units_map,
                            )
                            if fig:
                                st.plotly_chart(
                                    fig,
                                    width="stretch",
                                    config=plotly_config(filename=f"{device}_{rule.id}", fmt=plot_fmt),
                                    key=f"fig_{device}_{rule.id}",
                                )
                                shown += 1
                            else:
                                st.caption("No plot series for this result.")
            if shown == 0 and any(eq == device for eq, _rid in lookup):
                st.info(
                    "No FAULT plots to show — enable **Show PASS plots**, or check column mapping / run results."
                )

    with tabs[5]:
        st.subheader("Analytics")
        st.caption(
            "Per-motor run hours and mechanical cooling vs OAT histograms "
            "(chiller + DX compressor only — not cool-valve-only AHUs)."
        )
        a1, a2, a3 = st.columns(3)
        a1.metric("Fan / motor hours", f"{motor_tot['fan_hours']:.1f}")
        a2.metric("Pump hours", f"{motor_tot['pump_hours']:.1f}")
        a3.metric("Total", f"{motor_tot['total_hours']:.1f}")
        b1, b2, b3 = st.columns(3)
        b1.metric("Dataset start", start_s)
        b2.metric("Dataset end", end_s)
        b3.metric("Span (h)", f"{span['span_hours']:.1f}")
        st.markdown("##### Per-motor run hours")
        if motor_tbl.empty:
            st.info(
                "No fan_cmd / fan_status / pump command columns mapped yet. "
                "Map those roles on Data & Mapping, then return here."
            )
        else:
            st.dataframe(motor_tbl, width="stretch", height=360)
            st.download_button(
                "Download motor run hours CSV",
                to_csv_bytes(motor_tbl),
                "motor_run_hours.csv",
                key="dl_motor_hours",
            )
        st.markdown("##### Mechanical cooling hours by OAT bin")
        cool_fig2 = mech_cooling_oat_histogram(cool_bins)
        if cool_fig2 is None:
            st.info("No chiller / DX compressor signals available for OAT-bin histogram.")
        else:
            st.plotly_chart(
                cool_fig2,
                width="stretch",
                config=plotly_config(filename="mech_cooling_oat_bins_analytics"),
                key="analytics_cool_hist",
            )
            st.dataframe(cool_bins, hide_index=True, width="stretch", height=280)
            st.download_button(
                "Download mech cooling OAT bins CSV",
                to_csv_bytes(cool_bins),
                "mech_cooling_oat_bins.csv",
                key="dl_cool_bins",
            )

    with tabs[6]:
        st.subheader("Export")
        st.caption("Use the Plotly camera on charts for PNG/JPEG. CSV summary below.")
        results = st.session_state.batch_results
        if results:
            summary = results_summary_table(results)
            st.download_button("Summary CSV", to_csv_bytes(summary), "fdd_summary.csv")
        if st.session_state.column_map:
            st.download_button(
                "Haystack column map JSON",
                data=__import__("json").dumps(
                    to_haystack_document(st.session_state.column_map), indent=2
                ).encode(),
                file_name="column_map.json",
                mime="application/json",
                key="dl_colmap_export",
            )


if __name__ == "__main__":
    main()
