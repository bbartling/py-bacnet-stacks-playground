"""Run EnergyPlus on the host (Windows/Linux) without Docker/WSL.

Default exe on this machine: ``C:\\EnergyPlusV26-1-0\\energyplus.exe``.
Override with env ``ENERGYPLUS_EXE``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_WINDOWS_EXE = Path(r"C:\EnergyPlusV26-1-0\energyplus.exe")


def resolve_energyplus_exe(explicit: str | Path | None = None) -> Path:
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p.resolve()
        raise FileNotFoundError(f"ENERGYPLUS_EXE not found: {p}")
    env = (os.environ.get("ENERGYPLUS_EXE") or "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p.resolve()
        raise FileNotFoundError(f"ENERGYPLUS_EXE not found: {p}")
    if DEFAULT_WINDOWS_EXE.is_file():
        return DEFAULT_WINDOWS_EXE.resolve()
    which = shutil.which("energyplus")
    if which:
        return Path(which).resolve()
    raise FileNotFoundError(
        "No EnergyPlus executable. Set ENERGYPLUS_EXE or install to "
        r"C:\EnergyPlusV26-1-0\energyplus.exe"
    )


def native_energyplus_available() -> bool:
    try:
        resolve_energyplus_exe()
        return True
    except FileNotFoundError:
        return False


def run_energyplus_native(
    idf: Path,
    epw: Path,
    output_dir: Path,
    *,
    readvars: bool = True,
    timeout: int | None = 7200,
    exe: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Single-run EnergyPlus via local ``energyplus.exe`` (no Docker)."""
    ep_exe = resolve_energyplus_exe(exe)
    idf = Path(idf).resolve()
    epw = Path(epw).resolve()
    work = Path(output_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)

    # Sibling stage dir — keep inputs out of the noisy out folder
    stage = work.parent / f"{work.name}__stage_in"
    stage.mkdir(parents=True, exist_ok=True)
    staged_idf = stage / idf.name
    staged_epw = stage / epw.name
    if staged_idf.resolve() != idf:
        shutil.copy2(idf, staged_idf)
    if staged_epw.resolve() != epw:
        shutil.copy2(epw, staged_epw)

    cmd = [
        str(ep_exe),
        "-w",
        str(staged_epw),
        "-d",
        str(work),
    ]
    if readvars:
        cmd.append("-r")
    cmd.append(str(staged_idf))

    return subprocess.run(
        cmd,
        cwd=str(work),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
