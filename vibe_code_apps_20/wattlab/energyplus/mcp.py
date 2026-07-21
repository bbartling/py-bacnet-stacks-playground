"""Thin helpers mirroring EnergyPlus-MCP capabilities via Docker CLI / uv.

Prefer driving the same toolkit the MCP server uses when the vendor tree is present.
Full interactive MCP tool use is available via Cursor MCP config (see third_party/README.md).

WattLab's in-package surface is **simulate-via-Docker**. Inspect/modify/plot tools
from the LBNL EnergyPlus-MCP server require a cloned vendor tree + Cursor MCP —
they are not reimplemented here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from wattlab.config import DOCKER_IMAGE, ENERGYPLUS_MCP, THIRD_PARTY
from wattlab.energyplus.docker import (
    DockerUnavailable,
    docker_bin,
    docker_info_ok,
    ensure_image,
    image_present,
    run_energyplus,
)


def mcp_vendor_ready() -> bool:
    return (ENERGYPLUS_MCP / "energyplus-mcp-server").is_dir()


def mcp_vendor_readme() -> Path | None:
    readme = THIRD_PARTY / "README.md"
    return readme if readme.is_file() else None


def capability_status(*, probe_docker: bool = True) -> dict[str, Any]:
    """Honest capability report: image?, vendor clone?, simulate-only vs full MCP.

    Does not pull/build images. Optional Docker probe is best-effort and never raises.
    """
    vendor = mcp_vendor_ready()
    docker_ok = False
    img = False
    if probe_docker:
        try:
            docker_ok = docker_info_ok()
            img = image_present() if docker_ok else False
        except DockerUnavailable:
            docker_ok = False
            img = False
        except Exception:  # noqa: BLE001 — status must stay soft
            docker_ok = False
            img = False

    if img and vendor:
        mode = "full_mcp_available"
        note = (
            "Docker image present and vendor clone ready — WattLab can simulate; "
            "Cursor MCP can expose full inspect/modify/plot tools "
            "(see third_party/README.md)."
        )
    elif img:
        mode = "simulate_only"
        note = (
            "Docker image present — WattLab batch simulate works. "
            "Full LBNL MCP inspect/modify/plot tools need a vendor clone "
            f"at {ENERGYPLUS_MCP}."
        )
    elif vendor:
        mode = "vendor_only_no_image"
        note = (
            "Vendor clone present but Docker image missing — build "
            f"{DOCKER_IMAGE} per third_party/README.md before live sims."
        )
    else:
        mode = "unavailable"
        note = (
            "No Docker image and no vendor clone — install Docker, build "
            f"{DOCKER_IMAGE}, and optionally clone EnergyPlus-MCP for full MCP tools."
        )

    return {
        "image": DOCKER_IMAGE,
        "docker_available": docker_ok,
        "image_present": img,
        "vendor_present": vendor,
        "vendor_path": str(ENERGYPLUS_MCP),
        "vendor_readme": str(mcp_vendor_readme()) if mcp_vendor_readme() else None,
        "capability": mode,
        "simulate_via_docker": bool(img),
        "full_mcp_tools_available": bool(img and vendor),
        "note": note,
        "apihelper_note": (
            "EnergyPlusAPIHelper viz patterns (zone heatmap, OA charts) are adapted "
            "for post-sim eplusout.csv parsing; host-side pyenergyplus Runtime API "
            "is not required."
        ),
    }


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
    status = capability_status(probe_docker=True)
    if not status.get("image_present"):
        status["energyplus_ok"] = False
        status["energyplus_version"] = ""
        return status

    try:
        ensure_image(build=False)
        r = subprocess.run(
            [docker_bin(), "run", "--rm", DOCKER_IMAGE, "energyplus", "--version"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        status["energyplus_ok"] = r.returncode == 0
        status["energyplus_version"] = (r.stdout or r.stderr or "").strip()
    except Exception as exc:  # noqa: BLE001
        status["energyplus_ok"] = False
        status["energyplus_version"] = ""
        status["error"] = str(exc)

    if check_mcp_import and mcp_vendor_ready() and status.get("image_present"):
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


def align_idf_to_epw(
    idf: Path,
    epw: Path,
    out_idf: Path | None = None,
) -> dict[str, Any]:
    """Clip IDF RunPeriod to EPW data coverage (partial-year AMY safe).

    Returns metadata; ``out`` is the IDF path to simulate (may equal ``idf``
    when weather is a full calendar year and no clip is needed).
    """
    from wattlab.energyplus.patches import apply_run_period
    from wattlab.weather.epw import epw_data_period

    idf = Path(idf)
    epw = Path(epw)
    span = epw_data_period(epw)
    if not span:
        return {"patch": "run_period", "applied": False, "reason": "epw_span_unknown", "out": str(idf)}
    if span.get("partial_day_only") or span.get("ok") is False or not span.get("end"):
        return {
            "patch": "run_period",
            "applied": False,
            "reason": span.get("reason") or "partial_day_only",
            "epw_begin": span.get("begin"),
            "epw_end": span.get("end"),
            "last_row_hour": span.get("last_row_hour"),
            "end_clipped_from_partial_day": span.get("end_clipped_from_partial_day"),
            "out": str(idf),
        }
    if span.get("full_calendar_year"):
        return {
            "patch": "run_period",
            "applied": False,
            "reason": "full_calendar_year",
            "epw_begin": span["begin"],
            "epw_end": span["end"],
            "out": str(idf),
        }
    dest = Path(out_idf) if out_idf is not None else idf.with_name(f"{idf.stem}_epw_aligned.idf")
    # Prefer exact data-row dates (not header month/day without year).
    begin = span["begin"]
    end = span["end"]
    meta = apply_run_period(idf, dest, begin=begin, end=end)
    meta["applied"] = True
    meta["reason"] = (
        f"EPW data period {begin}→{end} is not a full calendar year; "
        "RunPeriod auto-clipped (partial-year AMY)."
    )
    meta["epw_begin"] = begin
    meta["epw_end"] = end
    meta["n_days"] = span.get("n_days")
    meta["last_row_hour"] = span.get("last_row_hour")
    meta["end_clipped_from_partial_day"] = span.get("end_clipped_from_partial_day")
    return meta


def simulate(
    idf: Path,
    epw: Path,
    output_dir: Path,
    *,
    timeout: int | None = 3600,
    align_run_period: bool = True,
) -> dict[str, Any]:
    """Run EnergyPlus simulation (parity with MCP run_energyplus_simulation).

    When ``align_run_period`` is True (default), partial-year EPWs auto-clip
    the IDF RunPeriod before Docker invoke — avoids FATAL GetNextEnvironment.
    """
    idf = Path(idf)
    epw = Path(epw)
    output_dir = Path(output_dir)
    align_meta: dict[str, Any] | None = None
    idf_run = idf
    if align_run_period:
        try:
            aligned_path = output_dir.parent / f"{output_dir.name}__epw_aligned.idf"
            # ensure parent exists for aligned idf (writable)
            from wattlab.energyplus.docker import ensure_ep_writable

            ensure_ep_writable(output_dir.parent)
            align_meta = align_idf_to_epw(idf, epw, out_idf=aligned_path)
            if align_meta.get("applied"):
                idf_run = Path(align_meta["out"])
        except Exception as exc:  # noqa: BLE001
            align_meta = {"patch": "run_period", "applied": False, "error": str(exc)}

    proc = run_energyplus(idf_run, epw, output_dir, timeout=timeout)
    out: dict[str, Any] = {
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
        "output_dir": str(output_dir),
        "ok": proc.returncode == 0,
        "idf_simulated": str(idf_run),
    }
    if align_meta is not None:
        out["run_period_align"] = align_meta
    return out


def copy_prototype(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def write_status_json(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(get_server_status_via_docker(), indent=2), encoding="utf-8")
    return path
