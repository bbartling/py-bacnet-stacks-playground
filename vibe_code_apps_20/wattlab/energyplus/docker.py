"""Docker helpers for the energyplus-mcp-dev image."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from wattlab.config import DOCKER_IMAGE, ENERGYPLUS_MCP, ROOT


class DockerUnavailable(RuntimeError):
    pass


class ImageMissing(RuntimeError):
    pass


def docker_bin() -> str:
    exe = shutil.which("docker")
    if not exe:
        raise DockerUnavailable("docker not found on PATH; install Docker Desktop and retry")
    return exe


def docker_info_ok() -> bool:
    try:
        r = subprocess.run(
            [docker_bin(), "info"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return r.returncode == 0
    except (DockerUnavailable, subprocess.TimeoutExpired, OSError):
        return False


def image_present(image: str | None = None) -> bool:
    tag = image or DOCKER_IMAGE
    r = subprocess.run(
        [docker_bin(), "images", "-q", tag],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return r.returncode == 0 and bool(r.stdout.strip())


def ensure_image(*, build: bool = False) -> str:
    """Return image name; optionally build from vendored EnergyPlus-MCP."""
    if image_present():
        return DOCKER_IMAGE
    if not build:
        raise ImageMissing(
            f"Docker image '{DOCKER_IMAGE}' not found. Build once from "
            f"{ENERGYPLUS_MCP}: docker build -t {DOCKER_IMAGE} "
            f"-f .devcontainer/Dockerfile .devcontainer"
        )
    if not ENERGYPLUS_MCP.is_dir():
        raise ImageMissing(
            f"Missing {ENERGYPLUS_MCP}. Clone per third_party/VERSION.txt then rebuild."
        )
    dockerfile_dir = ENERGYPLUS_MCP / ".devcontainer"
    cmd = [
        docker_bin(),
        "build",
        "-t",
        DOCKER_IMAGE,
        "-f",
        str(dockerfile_dir / "Dockerfile"),
        str(dockerfile_dir),
    ]
    subprocess.run(cmd, check=True, cwd=str(ENERGYPLUS_MCP))
    return DOCKER_IMAGE


def _win_mount(path: Path) -> str:
    """Docker Desktop on Windows accepts forward-slash absolute paths."""
    return str(path.resolve()).replace("\\", "/")


def run_in_container(
    cmd: list[str],
    *,
    workdir: str = "/workspace/app",
    mounts: list[tuple[Path, str]] | None = None,
    image: str | None = None,
    check: bool = True,
    timeout: int | None = 3600,
) -> subprocess.CompletedProcess[str]:
    """Run a command inside energyplus-mcp-dev with host dirs mounted."""
    ensure_image(build=False)
    tag = image or DOCKER_IMAGE
    args = [docker_bin(), "run", "--rm"]
    default_mounts: list[tuple[Path, str]] = [(ROOT, "/workspace/app")]
    if ENERGYPLUS_MCP.is_dir():
        default_mounts.append((ENERGYPLUS_MCP, "/workspace/EnergyPlus-MCP"))
    for host, container in mounts or default_mounts:
        args.extend(["-v", f"{_win_mount(host)}:{container}"])
    args.extend(["-w", workdir, tag, *cmd])
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def run_energyplus(
    idf: Path,
    epw: Path,
    output_dir: Path,
    *,
    timeout: int | None = 3600,
    readvars: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Annual (or IDF run-period) EnergyPlus simulate via Docker.

    ``readvars=True`` (default) passes ``-r`` so EnergyPlus writes
    ``eplusout.csv`` for Twin APIHelper-08 timeseries panes.
    Mount sources are translated via ``host_path_for_docker`` when Studio runs
    with docker.sock + ``WATTLAB_HOST_WORKSPACE``.
    """
    from wattlab.config import host_path_for_docker

    output_dir.mkdir(parents=True, exist_ok=True)
    idf = idf.resolve()
    epw = epw.resolve()
    work = output_dir.resolve()
    cmd = [
        "energyplus",
        "-w",
        f"/work/in/{epw.name}",
        "-d",
        "/work/out",
    ]
    if readvars:
        cmd.append("-r")
    cmd.append(f"/work/in/{idf.name}")
    # Put idf+epw copies next to a shared mount if they differ in parents.
    stage = work / "_stage_in"
    stage.mkdir(parents=True, exist_ok=True)
    staged_idf = stage / idf.name
    staged_epw = stage / epw.name
    if staged_idf.resolve() != idf:
        shutil.copy2(idf, staged_idf)
    if staged_epw.resolve() != epw:
        shutil.copy2(epw, staged_epw)
    host_stage = host_path_for_docker(stage)
    host_work = host_path_for_docker(work)
    args = [
        docker_bin(),
        "run",
        "--rm",
        "-v",
        f"{_win_mount(host_stage)}:/work/in",
        "-v",
        f"{_win_mount(host_work)}:/work/out",
        "-w",
        "/work/out",
        DOCKER_IMAGE,
        *cmd,
    ]
    ensure_image(build=False)
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
