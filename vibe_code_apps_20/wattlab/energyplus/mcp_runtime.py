"""Ensure EnergyPlus-MCP vendor + image; run MCP tools via docker (production path).

Agents use this the same way a human would: ``wattlab energyplus-ensure`` once per
host, then ``wattlab mcp-exec`` / ``wattlab dial-loads`` for IDF surgery. Annual
sims stay on WattLab DinD (``run_energyplus``).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from wattlab.config import (
    DOCKER_IMAGE,
    ROOT,
    THIRD_PARTY,
    artifacts_root,
    host_path_for_docker,
    resolve_energyplus_mcp_path,
)
from wattlab.energyplus.docker import (
    DockerUnavailable,
    docker_bin,
    docker_info_ok,
    image_present,
)


def parse_version_pin(pin_file: Path | None = None) -> dict[str, str]:
    """Parse ``third_party/VERSION.txt`` (repo URL, commit, image)."""
    path = pin_file or (THIRD_PARTY / "VERSION.txt")
    if not path.is_file():
        # Tip image may lack VERSION.txt beside workspace clone — fall back to ROOT
        alt = ROOT / "third_party" / "VERSION.txt"
        path = alt if alt.is_file() else path
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    repo = "https://github.com/LBNL-ETA/EnergyPlus-MCP"
    commit = ""
    image = DOCKER_IMAGE
    for line in text.splitlines():
        if line.lower().startswith("repo:"):
            repo = line.split(":", 1)[1].strip()
        elif line.lower().startswith("commit:"):
            commit = line.split(":", 1)[1].strip()
        elif line.lower().startswith("image:"):
            image = line.split(":", 1)[1].strip() or image
    return {"repo": repo, "commit": commit, "image": image, "pin_file": str(path)}


def default_vendor_target() -> Path:
    """Preferred clone destination for tip agents (shared workspace)."""
    env = (os.environ.get("WATTLAB_ENERGYPLUS_MCP") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    ws = (os.environ.get("WATTLAB_STUDIO_WORKSPACE") or "").strip()
    if ws:
        return Path(ws).expanduser().resolve() / "third_party" / "EnergyPlus-MCP"
    return (ROOT / "third_party" / "EnergyPlus-MCP").resolve()


def mcp_vendor_path() -> Path:
    return resolve_energyplus_mcp_path()


def mcp_vendor_ready(path: Path | None = None) -> bool:
    p = path or mcp_vendor_path()
    return (Path(p) / "energyplus-mcp-server").is_dir()


def _git_bin() -> str:
    exe = __import__("shutil").which("git")
    if not exe:
        raise RuntimeError("git not found on PATH — required to clone EnergyPlus-MCP")
    return exe


def clone_or_checkout_vendor(
    dest: Path | None = None,
    *,
    pin: dict[str, str] | None = None,
) -> Path:
    """Clone LBNL EnergyPlus-MCP at the pinned commit into ``dest``."""
    pin = pin or parse_version_pin()
    dest = Path(dest) if dest is not None else default_vendor_target()
    dest.parent.mkdir(parents=True, exist_ok=True)
    git = _git_bin()
    commit = (pin.get("commit") or "").strip()
    repo = pin["repo"]
    if not (dest / ".git").is_dir():
        if dest.exists() and any(dest.iterdir()):
            raise RuntimeError(
                f"Vendor path {dest} exists but is not a git clone. "
                "Remove it or set WATTLAB_ENERGYPLUS_MCP to a clean path."
            )
        subprocess.run(
            [git, "clone", repo, str(dest)],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    subprocess.run(
        [git, "-C", str(dest), "fetch", "--all", "--tags"],
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if commit:
        subprocess.run(
            [git, "-C", str(dest), "checkout", commit],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    if not (dest / "energyplus-mcp-server").is_dir():
        raise RuntimeError(f"Clone incomplete — missing energyplus-mcp-server under {dest}")
    return dest


def build_energyplus_image(vendor: Path | None = None) -> str:
    """Build ``energyplus-mcp-dev`` with explicit TARGETPLATFORM (required by upstream)."""
    vendor = Path(vendor) if vendor is not None else mcp_vendor_path()
    if not (vendor / ".devcontainer" / "Dockerfile").is_file():
        raise RuntimeError(
            f"Missing {vendor / '.devcontainer' / 'Dockerfile'}. "
            "Run wattlab energyplus-ensure first."
        )
    machine = platform.machine().lower()
    if machine in {"aarch64", "arm64"}:
        plat = "linux/arm64"
    else:
        plat = os.environ.get("TARGETPLATFORM") or "linux/amd64"
    cmd = [
        docker_bin(),
        "build",
        "--build-arg",
        f"TARGETPLATFORM={plat}",
        "-t",
        DOCKER_IMAGE,
        "-f",
        str(vendor / ".devcontainer" / "Dockerfile"),
        str(vendor / ".devcontainer"),
    ]
    subprocess.run(cmd, check=True, timeout=3600)
    return DOCKER_IMAGE


def energyplus_ensure(
    *,
    clone: bool = True,
    build: bool = True,
    dest: Path | None = None,
) -> dict[str, Any]:
    """Ensure vendor clone + Docker image. Fail loud — never soft-fall to sim-only."""
    pin = parse_version_pin()
    out: dict[str, Any] = {
        "pin": pin,
        "image": DOCKER_IMAGE,
        "vendor_path": None,
        "vendor_ready": False,
        "image_present": False,
        "docker_available": False,
        "actions": [],
        "ok": False,
    }
    if not docker_info_ok():
        out["error"] = (
            "Docker daemon not available. Install Docker and expose the sock to vibe20 "
            "(WATTLAB_HOST_WORKSPACE + /var/run/docker.sock)."
        )
        return out
    out["docker_available"] = True

    target = Path(dest) if dest is not None else default_vendor_target()
    if mcp_vendor_ready(target):
        vendor = target
        out["actions"].append("vendor_already_present")
    elif mcp_vendor_ready():
        vendor = mcp_vendor_path()
        out["actions"].append("vendor_found_via_resolve")
    elif clone:
        vendor = clone_or_checkout_vendor(target, pin=pin)
        out["actions"].append(f"cloned:{vendor}")
    else:
        out["error"] = (
            f"EnergyPlus-MCP vendor missing at {target}. "
            "Re-run: wattlab energyplus-ensure"
        )
        out["vendor_path"] = str(target)
        return out

    out["vendor_path"] = str(vendor)
    out["vendor_ready"] = mcp_vendor_ready(vendor)

    if image_present():
        out["image_present"] = True
        out["actions"].append("image_already_present")
    elif build:
        build_energyplus_image(vendor)
        out["image_present"] = image_present()
        out["actions"].append("built_image")
    else:
        out["error"] = (
            f"Docker image '{DOCKER_IMAGE}' missing. "
            "Re-run: wattlab energyplus-ensure  (builds once from vendor pin)"
        )
        return out

    out["ok"] = bool(out["vendor_ready"] and out["image_present"])
    if not out["ok"] and "error" not in out:
        out["error"] = "ensure incomplete — vendor or image still missing"
    return out


def _container_data_path(path: Path) -> str:
    """Map a host/container workspace path to ``/data/...`` inside mcp-exec."""
    p = Path(path).resolve()
    roots: list[Path] = []
    ws = (os.environ.get("WATTLAB_STUDIO_WORKSPACE") or "").strip()
    if ws:
        roots.append(Path(ws).expanduser().resolve())
    host_ws = (os.environ.get("WATTLAB_HOST_WORKSPACE") or "").strip()
    if host_ws:
        roots.append(Path(host_ws).expanduser().resolve())
    # Same fallback mcp_exec mounts when env vars are unset
    try:
        roots.append(artifacts_root().parent.resolve())
    except Exception:  # noqa: BLE001
        pass
    for root in roots:
        try:
            rel = p.relative_to(root)
            return "/data/" + rel.as_posix()
        except ValueError:
            continue
    return str(p).replace("\\", "/")


def mcp_exec(
    argv: list[str],
    *,
    timeout: int | None = 600,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run ``uv run <argv>`` inside energyplus-mcp-dev with vendor + /data mounts."""
    if not argv:
        raise ValueError("mcp_exec requires a command argv")
    if not docker_info_ok():
        raise DockerUnavailable("Docker daemon not available for mcp-exec")
    if not image_present():
        raise RuntimeError(
            f"Image '{DOCKER_IMAGE}' missing — run: wattlab energyplus-ensure"
        )
    vendor = mcp_vendor_path()
    if not mcp_vendor_ready(vendor):
        raise RuntimeError(
            f"Vendor missing at {vendor} — run: wattlab energyplus-ensure"
        )

    vendor_host = host_path_for_docker(vendor)
    ws = (os.environ.get("WATTLAB_STUDIO_WORKSPACE") or "").strip()
    host_ws = (os.environ.get("WATTLAB_HOST_WORKSPACE") or "").strip()
    if host_ws:
        data_host = Path(host_ws).expanduser().resolve()
    elif ws:
        data_host = host_path_for_docker(Path(ws))
    else:
        data_host = host_path_for_docker(artifacts_root().parent)

    cmd = [
        docker_bin(),
        "run",
        "--rm",
        "-v",
        f"{str(data_host).replace(chr(92), '/')}:/data",
        "-v",
        f"{str(vendor_host).replace(chr(92), '/')}:/workspace",
        "-w",
        "/workspace/energyplus-mcp-server",
        DOCKER_IMAGE,
        "uv",
        "run",
        *argv,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def dial_loads_via_docker(
    src_idf: Path,
    dst_idf: Path,
    *,
    lights_w_per_m2: float,
    equip_w_per_m2: float,
    infil_mult: float | None = None,
) -> dict[str, Any]:
    """Apply load dials inside energyplus-mcp-dev (no local EnergyPlusManager)."""
    src_idf = Path(src_idf).resolve()
    dst_idf = Path(dst_idf).resolve()
    dst_idf.parent.mkdir(parents=True, exist_ok=True)

    # Ensure paths live under workspace so /data mount sees them
    src_c = _container_data_path(src_idf)
    dst_c = _container_data_path(dst_idf)
    if not src_c.startswith("/data"):
        # Copy into artifacts so DinD mount can read
        art = artifacts_root() / "mcp_dial"
        art.mkdir(parents=True, exist_ok=True)
        staged_src = art / src_idf.name
        staged_src.write_bytes(src_idf.read_bytes())
        staged_dst = art / (dst_idf.stem + "_out.idf")
        src_c = _container_data_path(staged_src)
        dst_c = _container_data_path(staged_dst)
        copy_back = staged_dst
    else:
        copy_back = None

    infil_expr = "None" if infil_mult is None else repr(float(infil_mult))
    py = f"""
import json, shutil
from pathlib import Path
from energyplus_mcp_server.energyplus_tools import EnergyPlusManager

src = Path({src_c!r})
dst = Path({dst_c!r})
dst.parent.mkdir(parents=True, exist_ok=True)
tmp = dst.with_name(dst.stem + "_mcp_tmp.idf")
if tmp.exists():
    tmp.unlink()
shutil.copy2(src, tmp)
ep = EnergyPlusManager()
r1 = ep.modify_lights(str(tmp), [{{"target": "all", "field_updates": {{
    "Design_Level_Calculation_Method": "Watts/Area",
    "Watts_per_Floor_Area": {float(lights_w_per_m2)},
}}}}], output_path=str(tmp))
r2 = ep.modify_electric_equipment(str(tmp), [{{"target": "all", "field_updates": {{
    "Design_Level_Calculation_Method": "Watts/Area",
    "Watts_per_Floor_Area": {float(equip_w_per_m2)},
}}}}], output_path=str(tmp))
r3 = None
infil = {infil_expr}
if infil is not None and float(infil) != 1.0:
    r3 = ep.change_infiltration_by_mult(str(tmp), float(infil), output_path=str(tmp))
shutil.copy2(tmp, dst)
try:
    tmp.unlink()
except OSError:
    pass
print(json.dumps({{
    "lights": str(r1)[:500],
    "equip": str(r2)[:500],
    "infil": None if r3 is None else str(r3)[:500],
    "lights_w_per_m2": {float(lights_w_per_m2)},
    "equip_w_per_m2": {float(equip_w_per_m2)},
    "infil_mult": infil,
    "src": str(src),
    "dst": str(dst),
    "via": "mcp-exec",
}}))
"""
    proc = mcp_exec(["python", "-c", py], check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            "dial-loads via mcp-exec failed:\n"
            + (proc.stderr or "")[-2000:]
            + "\n"
            + (proc.stdout or "")[-1000:]
        )
    # Last JSON line
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip().startswith("{")]
    if not lines:
        raise RuntimeError(f"dial-loads mcp-exec returned no JSON: {(proc.stdout or '')[-500:]}")
    meta = json.loads(lines[-1])
    if copy_back is not None and copy_back.is_file():
        dst_idf.write_bytes(copy_back.read_bytes())
        meta["dst"] = str(dst_idf)
    meta["hint"] = (
        "High elec + low gas ⇒ cut internal gains / raise infil — not more 5Zone schedule patches."
    )
    return meta


def main_ensure(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wattlab energyplus-ensure",
        description="Clone pinned EnergyPlus-MCP + build energyplus-mcp-dev (once per host).",
    )
    p.add_argument("--dest", default=None, help="Vendor clone path (default: workspace/third_party)")
    p.add_argument("--no-clone", action="store_true")
    p.add_argument("--no-build", action="store_true")
    args = p.parse_args(argv)
    meta = energyplus_ensure(
        clone=not args.no_clone,
        build=not args.no_build,
        dest=Path(args.dest) if args.dest else None,
    )
    print(json.dumps(meta, indent=2))
    return 0 if meta.get("ok") else 1


def main_mcp_exec(argv: list[str] | None = None) -> int:
    """wattlab mcp-exec -- python -c '…'   (args after -- go to uv run)."""
    raw = list(argv) if argv is not None else sys.argv[1:]
    if raw and raw[0] == "--":
        raw = raw[1:]
    if not raw:
        print(
            "usage: wattlab mcp-exec -- <uv-run-args…>\n"
            "example: wattlab mcp-exec -- python -c \"import energyplus_mcp_server; print('ok')\"",
            file=sys.stderr,
        )
        return 2
    try:
        proc = mcp_exec(raw, check=False)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n", file=sys.stderr)
    return int(proc.returncode)
