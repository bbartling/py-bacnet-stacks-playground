#!/usr/bin/env python3
"""Stage provisional Lakeside W2A HP + mixed-water loop via HVACTemplate (E+ 26.1).

Replaces IdealLoads zone equipment with HVACTemplate:Zone:WaterToAirHeatPump and
adds MixedWaterLoop + Tower + Boiler (PROVISIONAL — not as-built GLHE / 67-unit map).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.idf_inspect import NINE_ZONES  # noqa: E402
from eplus_native.runner import energyplus_version, run_energyplus  # noqa: E402
from eplus_native.schedule_calendar_repair import repair_idf_file  # noqa: E402

PROVENANCE = "PROVISIONAL_W2A_HVACTEMPLATE"
HONESTY = (
    "Provisional Zone WSHP via HVACTemplate + MixedWaterLoop/Tower/Boiler — "
    "NOT as-built 67-unit GSHP/GLHE; curves ASSUMED; DSM NO-GO until raw gates."
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip_ideal_loads(text: str) -> str:
    """Remove IdealLoads + existing zone HVAC/thermostat so HVACTemplate can expand cleanly."""
    text = re.sub(r"ZONEHVAC:IDEALLOADSAIRSYSTEM,.*?;\s*", "", text, flags=re.I | re.S)
    text = re.sub(r"ZoneHVAC:EquipmentList,.*?;\s*", "", text, flags=re.I | re.S)
    text = re.sub(r"ZoneHVAC:EquipmentConnections,.*?;\s*", "", text, flags=re.I | re.S)
    # Existing dual-setpoint controls conflict with HVACTemplate thermostats
    text = re.sub(r"ZoneControl:Thermostat:StagedDualSetpoint,.*?;\s*", "", text, flags=re.I | re.S)
    text = re.sub(r"ZoneControl:Thermostat,.*?;\s*", "", text, flags=re.I | re.S)
    text = re.sub(r"ThermostatSetpoint:DualSetpoint,.*?;\s*", "", text, flags=re.I | re.S)
    # Timestep-legal schedule times (4 steps/h → multiples of 15 min)
    text = text.replace("Until: 14:40", "Until: 14:45")
    text = text.replace("Until: 13:30", "Until: 13:30")  # ok (half hour)
    return text


def _templates_from_example() -> str:
    ex = Path(r"C:\EnergyPlusV26-1-0\ExampleFiles\HVACTemplate-5ZoneWaterToAirHeatPumpTowerBoiler.idf")
    text = ex.read_text(encoding="utf-8", errors="replace")
    plant_chunks = []
    for pat in [
        r"HVACTemplate:Plant:MixedWaterLoop,.*?;",
        r"HVACTemplate:Plant:Boiler,.*?;",
        r"HVACTemplate:Plant:Tower,.*?;",
    ]:
        m = re.search(pat, text, re.I | re.S)
        if m:
            plant_chunks.append(m.group(0))
    thermostat = """HVACTemplate:Thermostat,
    Lakeside_AllZones_Tstat, !- Name
    SCH_HtgSP,               !- Heating Setpoint Schedule Name
    ,                        !- Constant Heating Setpoint
    SCH_ClgSP,               !- Cooling Setpoint Schedule Name
    ;                        !- Constant Cooling Setpoint
"""
    zm = re.search(r"HVACTemplate:Zone:WaterToAirHeatPump,.*?;", text, re.I | re.S)
    if not zm:
        raise RuntimeError("zone WSHP template not found in example")
    proto_lines = []
    for line in zm.group(0).splitlines():
        if "Supplemental Heating Coil Capacity" in line:
            line = re.sub(r"^(\s*)([^,]+)", r"\g<1>0", line)
        proto_lines.append(line)
    proto = "\n".join(proto_lines)

    zone_blocks = []
    for z in NINE_ZONES:
        lines = proto.splitlines()
        if len(lines) >= 3:
            lines[1] = re.sub(r"^(\s*)([^,]+)", lambda m: f"{m.group(1)}{z}", lines[1])
            lines[2] = re.sub(
                r"^(\s*)([^,]+)",
                lambda m: f"{m.group(1)}Lakeside_AllZones_Tstat",
                lines[2],
            )
        zone_blocks.append("\n".join(lines))
    return (
        "! === PROVISIONAL W2A HVACTemplate plant (ASSUMED curves; not GLHE; strip capacity=0) ===\n"
        + thermostat
        + "\n"
        + "\n\n".join(plant_chunks)
        + "\n\n"
        + "\n\n".join(zone_blocks)
        + "\n"
    )


def expand_objects(idf_path: Path, work_dir: Path) -> Path:
    """Run EnergyPlus ExpandObjects from the install dir (needs Energy+.idd)."""
    import subprocess

    eplus_root = Path(r"C:\EnergyPlusV26-1-0")
    exe = eplus_root / "ExpandObjects.exe"
    if not exe.is_file():
        raise FileNotFoundError(exe)
    work_dir.mkdir(parents=True, exist_ok=True)
    # ExpandObjects historically reads in.idf from its CWD (= E+ root)
    in_idf = eplus_root / "in.idf"
    expanded = eplus_root / "expanded.idf"
    # cleanup prior
    for p in (in_idf, expanded, eplus_root / "expandedidf.err"):
        if p.is_file():
            p.unlink()
    shutil.copy2(idf_path, in_idf)
    proc = subprocess.run(
        [str(exe)],
        cwd=str(eplus_root),
        capture_output=True,
        text=True,
        timeout=180,
    )
    (work_dir / "expandobjects_tail.txt").write_text(
        (proc.stdout or "")[-4000:] + "\n" + (proc.stderr or "")[-2000:],
        encoding="utf-8",
    )
    if not expanded.is_file():
        raise RuntimeError(f"ExpandObjects failed exit={proc.returncode}; no expanded.idf")
    out = work_dir / "expanded.idf"
    shutil.copy2(expanded, out)
    txt = out.read_text(encoding="utf-8", errors="replace")
    txt = re.sub(
        r"ZoneControl:Thermostat:StagedDualSetpoint,.*?;\s*",
        "",
        txt,
        flags=re.I | re.S,
    )
    out.write_text(txt, encoding="utf-8", newline="\n")
    return out


def stage_w2a(src_idf: Path, dst_idf: Path) -> Path:
    text = src_idf.read_text(encoding="utf-8", errors="replace")
    text = _strip_ideal_loads(text)
    # Ensure plant sizing on
    text = re.sub(
        r"(Do Plant Sizing Calculation\s*\n\s*)([^,;]+)",
        r"\1Yes",
        text,
        count=1,
        flags=re.I,
    )
    text = text.rstrip() + "\n\n" + _templates_from_example()
    # Alias building
    text = re.sub(
        r"(Building,\s*\n\s*)([^,]+)(\s*,)",
        r"\1Lakeside_ES\3",
        text,
        count=1,
        flags=re.I,
    )
    dst_idf.parent.mkdir(parents=True, exist_ok=True)
    dst_idf.write_text(text, encoding="utf-8", newline="\n")
    return dst_idf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", default=True)
    args = ap.parse_args()
    site = Path(os.environ["LAKESIDE_SITE_ROOT"])
    camp = site / "eplus" / "campaigns" / f"w2a_provisional_smoke_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    camp.mkdir(parents=True, exist_ok=True)
    # Start from schedule-repaired mid capacity
    parent = site / "eplus" / "campaigns" / "schedule_sanity_20260808T150000Z" / "staged_idfs" / "S3_cap_mid_2p7.idf"
    if not parent.is_file():
        champ = sorted((site / "eplus" / "campaigns").glob("freeze_pre_schedule_plant_*/champion_B_equip_mult_mid_model.idf"))[-1]
        parent = camp / "repaired_parent.idf"
        repair_idf_file(champ, parent, heating_capacity_mmbtu_h=2.7)
    staged = camp / "trial.idf"
    stage_w2a(parent, staged)
    expand_dir = camp / "expand"
    expanded = expand_objects(staged, expand_dir)
    shutil.copy2(expanded, camp / "trial_expanded.idf")
    epw = site / "eplus" / "weather" / "madison_amy_202508_202607.epw"
    print(f"SMOKE W2A expanded={expanded}", flush=True)
    man = run_energyplus(
        run_id=camp.name,
        scenario_id="w2a_provisional_smoke",
        idf_path=expanded,
        epw_path=epw,
        output_dir=camp / "sim",
        require_zero_severe=False,
        allow_staged_idf=True,
    )
    has_w2a = False
    exp_text = expanded.read_text(encoding="utf-8", errors="replace")
    has_w2a = "ZoneHVAC:WaterToAirHeatPump" in exp_text or "WaterToAirHeatPump" in exp_text
    summary = {
        "campaign_id": camp.name,
        "created_utc": _utc(),
        "provenance": PROVENANCE,
        "honesty": HONESTY,
        "idf_sha256": sha256_file(staged),
        "expanded_idf_sha256": sha256_file(expanded),
        "expanded_contains_w2a": has_w2a,
        "energyplus_version": energyplus_version(),
        "exit_code": man.exit_code,
        "accepted": man.accepted,
        "severe_count": man.severe_count,
        "fatal_count": man.fatal_count,
        "reject_reasons": list(man.reject_reasons or []),
        "runtime_sec": man.runtime_sec,
        "status": "succeeded" if man.exit_code == 0 and (camp / "sim" / "eplusmtr.csv").is_file() else "failed",
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    repo = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-w2a-provisional-smoke.json"
    repo.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
