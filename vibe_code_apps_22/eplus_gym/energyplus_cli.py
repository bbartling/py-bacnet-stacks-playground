"""Run EnergyPlus from the installed CLI (sizing / short-weather Track B smoke)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from eplus_gym.discover import energyplus_root_candidates


def energyplus_exe() -> Path:
    env = os.environ.get("ENERGYPLUS_EXE")
    if env and Path(env).is_file():
        return Path(env)
    which = shutil.which("energyplus")
    if which:
        return Path(which)
    for root in energyplus_root_candidates():
        for name in ("energyplus.exe", "energyplus"):
            cand = root / name
            if cand.is_file():
                return cand
    raise FileNotFoundError("energyplus executable not found; set ENERGYPLUS_EXE")


def run_energyplus_cli(
    *,
    idf: Path,
    epw: Path | None,
    output: Path,
    extra_args: list[str] | None = None,
    timeout_s: float = 3600.0,
) -> dict[str, Any]:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    exe = energyplus_exe()
    cmd = [str(exe), "-d", str(output)]
    if epw is not None:
        cmd += ["-w", str(Path(epw))]
    if extra_args:
        cmd += list(extra_args)
    cmd.append(str(Path(idf)))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-4000:],
        "output": str(output),
        "exe": str(exe),
    }
