"""Invoke EnergyPlus into an isolated run directory."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from eplus_native import (
    DEFAULT_COOL_COP,
    DEFAULT_EPLUS_EXE,
    DEFAULT_HEAT_COP,
    PROXY_FORMULA_VERSION,
)
from eplus_native.hashes import sha256_file
from eplus_native.manifest import RunManifest, utc_now
from eplus_native.validate import validate_run


def energyplus_version(exe: Path | str = DEFAULT_EPLUS_EXE) -> str:
    exe = Path(exe)
    if not exe.is_file():
        return "missing"
    try:
        proc = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        line = (proc.stdout or proc.stderr or "").strip().splitlines()
        return line[0] if line else f"exit={proc.returncode}"
    except Exception as e:
        return f"version_error:{e}"


def run_energyplus(
    *,
    run_id: str,
    scenario_id: str,
    idf_path: Path | str,
    epw_path: Path | str,
    output_dir: Path | str,
    exe: Path | str = DEFAULT_EPLUS_EXE,
    heat_cop: float = DEFAULT_HEAT_COP,
    cool_cop: float = DEFAULT_COOL_COP,
    require_zero_severe: bool = True,
    allow_staged_idf: bool = True,
) -> RunManifest:
    """Run EnergyPlus and return a validated RunManifest (may be rejected)."""
    idf = Path(idf_path)
    epw = Path(epw_path)
    out = Path(output_dir)
    exe_p = Path(exe)
    if not idf.is_file():
        raise FileNotFoundError(idf)
    if not epw.is_file():
        raise FileNotFoundError(epw)
    if not exe_p.is_file():
        raise FileNotFoundError(exe_p)

    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)

    # Keep a copy of the staged IDF next to outputs for provenance
    staged_copy = out.parent / "model.idf"
    if Path(idf).resolve() != staged_copy.resolve():
        shutil.copy2(idf, staged_copy)

    cmd = [str(exe_p), "-w", str(epw), "-d", str(out), "-r", str(idf)]
    started = utc_now()
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    runtime = time.perf_counter() - t0
    ended = utc_now()
    (out / "energyplus_tail.txt").write_text(
        (proc.stdout or "")[-6000:] + "\n" + (proc.stderr or "")[-3000:],
        encoding="utf-8",
    )

    manifest = RunManifest(
        run_id=run_id,
        scenario_id=scenario_id,
        idf_path=str(idf.resolve()),
        idf_sha256=sha256_file(idf),
        epw_path=str(epw.resolve()),
        epw_sha256=sha256_file(epw),
        energyplus_exe=str(exe_p),
        energyplus_version=energyplus_version(exe_p),
        command=cmd,
        started_utc=started,
        ended_utc=ended,
        runtime_sec=round(runtime, 3),
        exit_code=int(proc.returncode),
        output_dir=str(out.resolve()),
        warning_count=-1,
        severe_count=-1,
        fatal_count=-1,
        heat_cop=float(heat_cop),
        cool_cop=float(cool_cop),
        proxy_formula_version=PROXY_FORMULA_VERSION,
        extras={"allow_staged_idf": allow_staged_idf},
    )
    manifest = validate_run(manifest, require_zero_severe=require_zero_severe)
    manifest.write(out.parent / "run_manifest.json")
    (out / "run_result.json").write_text(
        json.dumps(
            {
                "success": manifest.accepted,
                "returncode": manifest.exit_code,
                "severe_count": manifest.severe_count,
                "fatal_count": manifest.fatal_count,
                "provenance": manifest.provenance,
                "reject_reasons": manifest.reject_reasons,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest
