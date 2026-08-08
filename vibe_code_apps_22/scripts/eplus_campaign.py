#!/usr/bin/env python
"""Run GL14 calibration iterations with BAS / deep-research informed knobs.

Uses EnergyPlus 26.1 (same engine as EnergyPlus-MCP). Knobs mirror MCP tools
plus architecture dials: WWR, window U, wall/roof insulation conductivity,
infiltration, LPD/EPD/people, heat/cool COP proxy.
"""
from __future__ import annotations


import sys
from pathlib import Path as _PathForLakeside

_APP = _PathForLakeside(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
from lakeside.paths import (  # noqa: E402
    BUILDING_LABEL,
    CAMPUS_ID,
    REGION_LABEL,
    app_root,
    clean_data_building_dir,
    eplus_dir,
    packages_dir,
    reports_dir,
    resolve_eplus_model,
    site_root,
    utilities_dir,
)
from lakeside.paths import BUILDING_ID as _LAKESIDE_BUILDING_ID  # noqa: E402
from lakeside.paths import SITE_REF as _LAKESIDE_SITE_REF  # noqa: E402
APP = app_root()
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Deferred site paths — importing apply_knobs must work without LAKESIDE_SITE_ROOT (CI).
ROOT: Path | None = None
EPLUS: Path | None = None
MODELS: Path | None = None
RUNS: Path | None = None
LOG: Path | None = None
LEDGER: Path | None = None
SEED: Path | None = None
LATEST: Path | None = None
BEST: Path | None = None
PINNED_BEST: Path | None = None
BEST_SC: Path | None = None
AMY: Path | None = None
TMY: Path | None = None
EXE = Path(r"C:\EnergyPlusV26-1-0\energyplus.exe")
IDD = Path(r"C:\EnergyPlusV26-1-0\Energy+.idd")
MCP_VENV: Path | None = None


def _ensure_site_globals() -> Path:
    """Resolve site-rooted paths on first use (not at import)."""
    global ROOT, EPLUS, MODELS, RUNS, LOG, LEDGER, SEED, LATEST, BEST
    global PINNED_BEST, BEST_SC, AMY, TMY, MCP_VENV
    if ROOT is not None:
        return ROOT
    ROOT = site_root()
    EPLUS = ROOT / "eplus"
    MODELS = EPLUS / "models"
    RUNS = EPLUS / "runs"
    LOG = EPLUS / "scorecards" / "campaign_log.csv"
    LEDGER = EPLUS / "assumptions" / "ledger.json"
    SEED = resolve_eplus_model("lakeside_6zone_gshp_v0.idf")
    if not SEED.is_file():
        SEED = resolve_eplus_model("lakeside_6zone_gshp_best.idf")
    LATEST = MODELS / "lakeside_6zone_gshp_latest.idf"
    BEST = MODELS / "lakeside_6zone_gshp_best.idf"
    PINNED_BEST = resolve_eplus_model("lakeside_6zone_gshp_best.idf")
    BEST_SC = EPLUS / "scorecards" / "best_scorecard.json"
    AMY = EPLUS / "weather" / "madison_amy_202508_202607.epw"
    TMY = EPLUS / "weather" / "madison_tmy_screening.epw"
    MCP_VENV = ROOT.parent / "EnergyPlus-MCP" / "energyplus-mcp-server" / ".venv" / "Lib" / "site-packages"
    return ROOT


sys.path.insert(0, str(APP / "scripts"))


def _scale_after_method(text: str, method: str, mult: float, starts: tuple[str, ...]) -> str:
    starts_u = tuple(s.upper() for s in starts)
    lines = text.splitlines()
    out, in_obj, expect = [], False, False
    for line in lines:
        stripped = line.strip().upper()
        if any(stripped.startswith(s) for s in starts_u):
            in_obj = True
        if in_obj and method in line and "!" in line:
            if method in line.split("!")[0]:
                expect = True
            out.append(line)
            continue
        if expect and re.match(r"^\s*[0-9.]+", line):
            m = re.match(r"^(\s*)([0-9.]+)(.*)$", line)
            if m:
                line = f"{m.group(1)}{float(m.group(2)) * mult:.5f}{m.group(3)}"
            expect = False
        if in_obj and line.strip().endswith(";"):
            in_obj = False
            expect = False
        out.append(line)
    return "\n".join(out)


def _set_simple_glazing(text: str, u: float | None = None, shgc: float | None = None) -> str:
    lines = text.splitlines()
    out, in_obj, field_i = [], False, 0
    for line in lines:
        if line.strip().upper().startswith("WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM"):
            in_obj = True
            field_i = 0
            out.append(line)
            continue
        if in_obj:
            if "!" in line and re.match(r"^\s*[0-9.eE+-]", line):
                field_i += 1
                m = re.match(r"^(\s*)([0-9.eE+-]+)(.*)$", line)
                if m and field_i == 1 and u is not None:
                    line = f"{m.group(1)}{u:.4f}{m.group(3)}"
                elif m and field_i == 2 and shgc is not None:
                    line = f"{m.group(1)}{shgc:.4f}{m.group(3)}"
            if line.strip().endswith(";"):
                in_obj = False
        out.append(line)
    return "\n".join(out)


def _scale_material_conductivity(text: str, mat_name: str, mult: float) -> str:
    lines = text.splitlines()
    out, in_obj, after_name, thick_seen = [], False, False, False
    for line in lines:
        if line.strip().upper().startswith("MATERIAL,"):
            in_obj = True
            after_name = False
            thick_seen = False
            out.append(line)
            continue
        if in_obj:
            if not after_name and mat_name.lower() in line.split("!")[0].strip().rstrip(",").lower():
                after_name = True
            elif after_name and re.match(r"^\s*[0-9.]", line):
                # thickness then conductivity
                if not thick_seen:
                    thick_seen = True
                else:
                    m = re.match(r"^(\s*)([0-9.]+)(.*)$", line)
                    if m:
                        line = f"{m.group(1)}{float(m.group(2)) * mult:.5f}{m.group(3)}"
                    after_name = False
            if line.strip().endswith(";"):
                in_obj = False
                after_name = False
        out.append(line)
    return "\n".join(out)


def _apply_wwr_eppy(idf_text: str, wwr: float) -> str:
    """Rebuild fenestration verts from parent walls at target WWR."""
    if MCP_VENV.is_dir() and str(MCP_VENV) not in sys.path:
        sys.path.insert(0, str(MCP_VENV))
    from eppy.modeleditor import IDF
    from eplus_seed_6zone import _pt  # noqa: WPS433

    IDF.setiddname(str(IDD))
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.idf"
        p.write_text(idf_text, encoding="utf-8")
        idf = IDF(str(p))
        walls = {s.Name: s for s in idf.idfobjects.get("BUILDINGSURFACE:DETAILED", [])
                 if str(s.Surface_Type).lower() == "wall"}
        for fen in list(idf.idfobjects.get("FENESTRATIONSURFACE:DETAILED", [])):
            wall = walls.get(fen.Building_Surface_Name)
            if wall is None:
                continue
            bl = (float(wall.Vertex_1_Xcoordinate), float(wall.Vertex_1_Ycoordinate), float(wall.Vertex_1_Zcoordinate))
            br = (float(wall.Vertex_2_Xcoordinate), float(wall.Vertex_2_Ycoordinate), float(wall.Vertex_2_Zcoordinate))
            tl = (float(wall.Vertex_4_Xcoordinate), float(wall.Vertex_4_Ycoordinate), float(wall.Vertex_4_Zcoordinate))
            sill, head = 0.12, 0.88
            h_frac = head - sill
            w_frac = min(0.92, max(0.05, float(wwr) / h_frac))
            u0 = (1.0 - w_frac) / 2.0
            u1 = u0 + w_frac
            verts = [
                _pt(bl, br, tl, u0, sill),
                _pt(bl, br, tl, u1, sill),
                _pt(bl, br, tl, u1, head),
                _pt(bl, br, tl, u0, head),
            ]
            for i, (x, y, z) in enumerate(verts, 1):
                setattr(fen, f"Vertex_{i}_Xcoordinate", x)
                setattr(fen, f"Vertex_{i}_Ycoordinate", y)
                setattr(fen, f"Vertex_{i}_Zcoordinate", z)
        outp = Path(td) / "out.idf"
        idf.saveas(str(outp))
        return outp.read_text(encoding="utf-8")


def apply_knobs(idf_text: str, knobs: dict) -> str:
    text = idf_text
    if "lights_mult" in knobs:
        text = _scale_after_method(text, "Watts/Area", knobs["lights_mult"], ("LIGHTS,",))
    if "equip_mult" in knobs:
        text = _scale_after_method(text, "Watts/Area", knobs["equip_mult"], ("ELECTRICEQUIPMENT,",))
    if "people_mult" in knobs:
        text = _scale_after_method(text, "People/Area", knobs["people_mult"], ("PEOPLE,",))
    if "infil_mult" in knobs:
        text = _scale_after_method(
            text, "Flow/ExteriorArea", knobs["infil_mult"], ("ZONEINFILTRATION:DESIGNFLOWRATE,",)
        )
    if "window_u" in knobs or "window_shgc" in knobs:
        text = _set_simple_glazing(text, knobs.get("window_u"), knobs.get("window_shgc"))
    if "wall_k_mult" in knobs:
        text = _scale_material_conductivity(text, "Mat_Insul", knobs["wall_k_mult"])
    if "roof_k_mult" in knobs:
        text = _scale_material_conductivity(text, "Mat_RoofIns", knobs["roof_k_mult"])
    if "wwr" in knobs:
        text = _apply_wwr_eppy(text, float(knobs["wwr"]))
    return text


def run_sim(idf_path: Path, epw: Path, out_dir: Path) -> bool:
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(EXE), "-w", str(epw), "-d", str(out_dir), "-r", str(idf_path)],
        capture_output=True,
        text=True,
    )
    (out_dir / "energyplus_tail.txt").write_text(
        (proc.stdout or "")[-4000:] + "\n" + (proc.stderr or "")[-2000:], encoding="utf-8"
    )
    ok = proc.returncode == 0
    (out_dir / "run_result.json").write_text(
        json.dumps({"success": ok, "returncode": proc.returncode}, indent=2), encoding="utf-8"
    )
    return ok


def iteration_plan() -> list[dict]:
    """Phase D: 9-zone program peel (Gym/Cafe/Library) on research fenestration."""
    plan: list[dict] = []
    # 9-zone seed baseline (WWR 0.32 / U-0.35 IP baked in) + iter-5 infil×1.2
    plan.append({
        "iter": 75, "weather": "amy",
        "knobs": {"infil_mult": 1.2},
        "hypothesis": "amy_9zone_program_peel_I1.2",
    })
    plan.append({
        "iter": 76, "weather": "amy",
        "knobs": {"infil_mult": 1.2, "window_shgc": 0.38},
        "hypothesis": "amy_9zone_SHGC0.38_I1.2",
    })
    plan.append({
        "iter": 77, "weather": "amy",
        "knobs": {"infil_mult": 1.0},
        "hypothesis": "amy_9zone_I1.0_baseline_infil",
    })
    plan.append({
        "iter": 78, "weather": "amy",
        "knobs": {"infil_mult": 1.2, "lights_mult": 0.9},
        "hypothesis": "amy_9zone_I1.2_L0.9_warm_trim",
    })
    plan.append({
        "iter": 79, "weather": "amy",
        "knobs": {"infil_mult": 1.2, "equip_mult": 0.9},
        "hypothesis": "amy_9zone_I1.2_E0.9_warm_trim",
    })
    plan.append({
        "iter": 80, "weather": "amy",
        "knobs": {"infil_mult": 1.2, "lights_mult": 0.85, "equip_mult": 0.85},
        "hypothesis": "amy_9zone_I1.2_L0.85_E0.85",
    })
    return plan


def append_log(row: dict) -> None:
    _ensure_site_globals()
    assert LOG is not None
    LOG.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "iter", "hypothesis", "weather", "nmbe_pct", "cvrmse_pct",
        "gl14_status", "gl14_distance", "heat_cop", "cool_cop", "knobs_json",
    ]
    write_header = not LOG.is_file()
    with LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        w.writerow({k: row.get(k) for k in fields})


def update_ledger(entry: dict) -> None:
    _ensure_site_globals()
    assert LEDGER is not None
    data = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.is_file() else {
        "version": 1, "iterations": []
    }
    data.setdefault("iterations", []).append(entry)
    kn = entry.get("knobs") or {}
    if "heat_cop" in kn:
        data["heat_cop_proxy"] = kn["heat_cop"]
    if "cool_cop" in kn:
        data["cool_cop_proxy"] = kn["cool_cop"]
    LEDGER.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> int:
    from eplus_score_run import score_run

    _ensure_site_globals()
    assert LOG is not None and SEED is not None and LEDGER is not None
    assert RUNS is not None and LATEST is not None and AMY is not None and TMY is not None
    assert BEST is not None and BEST_SC is not None
    max_iter = int(os.environ.get("EPLUS_MAX_ITER", "80"))
    start_iter = int(os.environ.get("EPLUS_START_ITER", "75"))
    if LOG.is_file() and start_iter == 1:
        LOG.unlink()
    seed_text = SEED.read_text(encoding="utf-8")
    passes = 0
    best_dist = float("inf")
    best_idf = None
    best_sc = None
    if BEST_SC.is_file():
        try:
            prev = json.loads(BEST_SC.read_text(encoding="utf-8"))
            d = prev.get("gl14_distance")
            if isinstance(d, (int, float)) and d == d:
                best_dist = float(d)
                print(f"holding prior best distance={best_dist} ({prev.get('iter')})", flush=True)
        except Exception:
            pass

    for step in iteration_plan():
        n = step["iter"]
        if n < start_iter or n > max_iter:
            continue
        print(f"\n=== ITER {n:02d} {step['hypothesis']} ===", flush=True)
        knobs = dict(step["knobs"])
        led = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.is_file() else {
            "version": 1, "heat_cop_proxy": 3.5, "cool_cop_proxy": 4.5, "iterations": []
        }
        if "heat_cop" in knobs:
            led["heat_cop_proxy"] = knobs["heat_cop"]
        if "cool_cop" in knobs:
            led["cool_cop_proxy"] = knobs["cool_cop"]
        LEDGER.write_text(json.dumps(led, indent=2), encoding="utf-8")

        text = apply_knobs(seed_text, knobs)
        run_dir = RUNS / f"iter_{n:02d}"
        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)
        run_dir.mkdir(parents=True)
        idf_path = run_dir / "model.idf"
        idf_path.write_text(text, encoding="utf-8")
        LATEST.write_text(text, encoding="utf-8")

        epw = AMY if step["weather"] == "amy" else TMY
        sim_out = run_dir / "sim"
        ok = run_sim(idf_path, epw, sim_out)
        if not ok:
            print("sim failed — logging insufficient_data", flush=True)
            append_log({
                "iter": n, "hypothesis": step["hypothesis"], "weather": step["weather"],
                "nmbe_pct": "", "cvrmse_pct": "", "gl14_status": "sim_fail",
                "gl14_distance": "", "heat_cop": led.get("heat_cop_proxy"),
                "cool_cop": led.get("cool_cop_proxy"), "knobs_json": json.dumps(knobs),
            })
            continue

        sc = score_run(sim_out, iter_id=f"iter_{n:02d}")
        (run_dir / "scorecard.json").write_text(json.dumps(sc, indent=2), encoding="utf-8")
        gl = sc.get("gl14") or {}
        append_log({
            "iter": n,
            "hypothesis": step["hypothesis"],
            "weather": step["weather"],
            "nmbe_pct": gl.get("nmbe_pct"),
            "cvrmse_pct": gl.get("cvrmse_pct"),
            "gl14_status": sc.get("gl14_status"),
            "gl14_distance": sc.get("gl14_distance"),
            "heat_cop": knobs.get("heat_cop", led.get("heat_cop_proxy", 3.5)),
            "cool_cop": knobs.get("cool_cop", led.get("cool_cop_proxy", 4.5)),
            "knobs_json": json.dumps(knobs),
        })
        update_ledger({
            "iter": n,
            "hypothesis": step["hypothesis"],
            "knobs": knobs,
            "gl14_status": sc.get("gl14_status"),
            "gl14": gl,
            "bas_notes": (
                "Architecture knobs (WWR/window U/wall k/infil) + BAS zn_t / Semco OA+ERV; "
                "deep-research 2008 envelope baseline"
            ),
        })
        dist = sc.get("gl14_distance")
        print(
            f"iter={n} status={sc.get('gl14_status')} "
            f"NMBE={gl.get('nmbe_pct')} CVRMSE={gl.get('cvrmse_pct')} dist={dist}",
            flush=True,
        )
        if isinstance(dist, (int, float)) and dist == dist and dist < best_dist:
            best_dist = float(dist)
            best_idf = text
            best_sc = sc
            BEST.write_text(text, encoding="utf-8")
            BEST_SC.write_text(json.dumps(sc, indent=2), encoding="utf-8")
        if sc.get("gl14_status") == "pass":
            passes += 1
            if passes >= 2:
                print("Early stop: 2 G14 confirmation passes")
                break

    if best_idf:
        LATEST.write_text(best_idf, encoding="utf-8")
    if best_sc:
        BEST_SC.write_text(json.dumps(best_sc, indent=2), encoding="utf-8")
    print(f"campaign log: {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
