"""Thin helpers mirroring EnergyPlus-MCP capabilities via Docker CLI / uv.

Prefer driving the same toolkit the MCP server uses when the vendor tree is present.
Full interactive MCP tool use is available via Cursor MCP config (see third_party/README.md).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from wattlab.config import DOCKER_IMAGE, ENERGYPLUS_MCP
from wattlab.energyplus.docker import docker_bin, ensure_image, run_energyplus


def mcp_vendor_ready() -> bool:
    return (ENERGYPLUS_MCP / "energyplus-mcp-server").is_dir()


def cursor_mcp_config_snippet(host_mcp_path: Path | None = None) -> dict[str, Any]:
    root = host_mcp_path or ENERGYPLUS_MCP
    win = str(root.resolve()).replace("\\", "\\\\")
    return {
        "mcpServers": {
            "energyplus": {
                "command": "docker",
                "args": [
                    "run",
                    "--rm",
                    "-i",
                    "-v",
                    f"{win}:/workspace",
                    "-w",
                    "/workspace/energyplus-mcp-server",
                    DOCKER_IMAGE,
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "energyplus_mcp_server.server",
                ],
            }
        }
    }


def get_server_status_via_docker(*, check_mcp_import: bool = False) -> dict[str, Any]:
    """Smoke the container EnergyPlus binary (optional heavy MCP import)."""
    ensure_image(build=False)
    r = subprocess.run(
        [docker_bin(), "run", "--rm", DOCKER_IMAGE, "energyplus", "--version"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    status = {
        "image": DOCKER_IMAGE,
        "energyplus_ok": r.returncode == 0,
        "energyplus_version": (r.stdout or r.stderr or "").strip(),
        "vendor_present": mcp_vendor_ready(),
    }
    if check_mcp_import and mcp_vendor_ready():
        mount = str(ENERGYPLUS_MCP.resolve()).replace("\\", "/")
        ir = subprocess.run(
            [
                docker_bin(),
                "run",
                "--rm",
                "-v",
                f"{mount}:/workspace",
                "-w",
                "/workspace/energyplus-mcp-server",
                DOCKER_IMAGE,
                "uv",
                "run",
                "python",
                "-c",
                "import energyplus_mcp_server; print('mcp_import_ok')",
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        status["mcp_import_ok"] = ir.returncode == 0 and "mcp_import_ok" in (ir.stdout or "")
        status["mcp_import_stderr"] = (ir.stderr or "")[-500:]
    return status


def simulate(
    idf: Path,
    epw: Path,
    output_dir: Path,
    *,
    timeout: int | None = 3600,
) -> dict[str, Any]:
    """Run EnergyPlus simulation (parity with MCP run_energyplus_simulation)."""
    proc = run_energyplus(idf, epw, output_dir, timeout=timeout)
    return {
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
        "output_dir": str(output_dir),
        "ok": proc.returncode == 0,
    }


def copy_prototype(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def write_status_json(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(get_server_status_via_docker(), indent=2), encoding="utf-8")
    return path
