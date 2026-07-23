"""Docker helpers for the energyplus-mcp-dev image."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from wattlab.config import DOCKER_IMAGE, ROOT, resolve_energyplus_mcp_path

# energyplus-mcp-dev image runs as vscode (uid 1000). Studio DinD often creates
# bind-mounted dirs as root 755 → E+ cannot write eplusout.* under /work/out.
_DEFAULT_EP_USER = "1000:1000"


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
    vendor = resolve_energyplus_mcp_path()
    if not build:
        raise ImageMissing(
            f"Docker image '{DOCKER_IMAGE}' not found. Run: wattlab energyplus-ensure "
            f"(or build from {vendor})"
        )
    if not vendor.is_dir():
        raise ImageMissing(f"Missing {vendor}. Run: wattlab energyplus-ensure")
    from wattlab.energyplus.mcp_runtime import build_energyplus_image

    return build_energyplus_image(vendor)


def _win_mount(path: Path) -> str:
    """Docker Desktop on Windows accepts forward-slash absolute paths."""
    return str(path.resolve()).replace("\\", "/")


def ensure_ep_writable(path: Path) -> Path:
    """Create ``path`` world-writable so E+ container uid 1000 can write outputs.

    Studio often runs as root and creates 755 dirs; energyplus-mcp-dev is uid 1000.
    """
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o777)
    except OSError:
        pass
    return path


def _chmod_loose(path: Path, mode: int = 0o666) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def energyplus_docker_user() -> str | None:
    """User for ``docker run --user``. Default 1000:1000; set empty to disable."""
    raw = os.environ.get("ENERGYPLUS_DOCKER_USER")
    if raw is None:
        return _DEFAULT_EP_USER
    raw = raw.strip()
    return raw or None


def write_progress(
    progress_dir: Path | str | None,
    *,
    percent: int,
    status: str,
    note: str | None = None,
) -> None:
    """Atomically write ``progress.json`` for Twin APIHelper-08 live panes."""
    if progress_dir is None:
        return
    root = Path(progress_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        payload: dict = {
            "percent": max(0, min(100, int(percent))),
            "status": str(status),
        }
        if note:
            payload["note"] = note
        tmp = root / "progress.json.tmp"
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(root / "progress.json")
    except OSError:
        pass


def heuristic_ep_percent(line: str, current: int) -> int:
    """Bump progress from EnergyPlus console tokens (best-effort)."""
    low = line.lower()
    pct = current
    if "warmup" in low and pct < 15:
        pct = max(pct, 10)
    if "starting simulation" in low or "begin simulation" in low:
        pct = max(pct, 25)
    if "simulating" in low or "processing weather" in low:
        pct = max(pct, 35)
    # Month-ish tokens
    months = (
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    )
    for i, m in enumerate(months):
        if m in low:
            pct = max(pct, 40 + int((i + 1) * 4.5))
    if "readvars" in low or "writing tabular" in low or "csv" in low:
        pct = max(pct, 90)
    if "energyplus completed" in low or "======= final" in low:
        pct = max(pct, 98)
    return min(99, pct)


def _run_docker_streaming(
    args: list[str],
    *,
    timeout: int | None,
    progress_dir: Path | None,
) -> subprocess.CompletedProcess[str]:
    """Popen docker; stream lines to log + progress.json when progress_dir set."""
    import time

    write_progress(progress_dir, percent=1, status="running", note="docker starting")
    log_path = Path(progress_dir) / "console.log" if progress_dir else None
    if log_path is not None:
        try:
            log_path.write_text("", encoding="utf-8")
        except OSError:
            log_path = None

    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    chunks: list[str] = []
    percent = 1
    started = time.monotonic()
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            chunks.append(line)
            if log_path is not None:
                try:
                    with log_path.open("a", encoding="utf-8", errors="replace") as fh:
                        fh.write(line)
                except OSError:
                    pass
            percent = heuristic_ep_percent(line, percent)
            write_progress(progress_dir, percent=percent, status="running")
            if timeout is not None and (time.monotonic() - started) > timeout:
                proc.kill()
                write_progress(progress_dir, percent=percent, status="failed", note="timeout")
                break
        rc = proc.wait(timeout=30)
    except Exception as exc:  # noqa: BLE001
        try:
            proc.kill()
        except OSError:
            pass
        write_progress(progress_dir, percent=percent, status="failed", note=str(exc))
        return subprocess.CompletedProcess(args, returncode=1, stdout="".join(chunks), stderr=str(exc))

    out = "".join(chunks)
    if rc == 0:
        write_progress(progress_dir, percent=100, status="ok")
    else:
        write_progress(progress_dir, percent=percent, status="failed", note=f"returncode={rc}")
    return subprocess.CompletedProcess(args, returncode=rc, stdout=out, stderr="")


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
    user = energyplus_docker_user()
    if user:
        args.extend(["--user", user])
    default_mounts: list[tuple[Path, str]] = [(ROOT, "/workspace/app")]
    _vendor = resolve_energyplus_mcp_path()
    if _vendor.is_dir():
        default_mounts.append((_vendor, "/workspace/EnergyPlus-MCP"))
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
    progress_dir: Path | str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Annual (or IDF run-period) EnergyPlus simulate via Docker.

    ``readvars=True`` (default) passes ``-r`` so EnergyPlus writes
    ``eplusout.csv`` for Twin APIHelper-08 timeseries panes.
    When ``progress_dir`` is set, streams console into that folder's
    ``console.log`` / ``progress.json`` for live Twin panes.
    Mount sources are translated via ``host_path_for_docker`` when Studio runs
    with docker.sock + ``WATTLAB_HOST_WORKSPACE``.

    Output/stage dirs are chmod'd world-writable and the container runs as
    ``ENERGYPLUS_DOCKER_USER`` (default ``1000:1000``) so DinD from a root
    Studio process can write under ``/work/out``.
    """
    from wattlab.config import host_path_for_docker

    ensure_ep_writable(output_dir)
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
    # Sibling stage dir — NOT nested under output_dir. Nested mounts break
    # ReadVars (-r): EnergyPlus cannot write /work/in/*.rvi when /work/in is a
    # child of the /work/out volume (DinD host-path resolution).
    stage = work.parent / f"{work.name}__stage_in"
    ensure_ep_writable(stage)
    staged_idf = stage / idf.name
    staged_epw = stage / epw.name
    if staged_idf.resolve() != idf:
        shutil.copy2(idf, staged_idf)
    if staged_epw.resolve() != epw:
        shutil.copy2(epw, staged_epw)
    # Stage Schedule:File CSVs referenced as /work/in/<basename> (DinD contract).
    try:
        from wattlab.energyplus.patches.weather_schedules import (
            schedule_file_basenames_in_idf,
        )

        idf_text = staged_idf.read_text(encoding="utf-8", errors="replace")
        for base in schedule_file_basenames_in_idf(idf_text):
            src_csv = idf.parent / base
            if not src_csv.is_file():
                # Sidecar may sit next to original IDF before copy.
                alt = Path(idf).parent / base
                src_csv = alt if alt.is_file() else src_csv
            if src_csv.is_file():
                dest_csv = stage / base
                if dest_csv.resolve() != src_csv.resolve():
                    shutil.copy2(src_csv, dest_csv)
                _chmod_loose(dest_csv)
    except OSError:
        pass
    _chmod_loose(staged_idf)
    _chmod_loose(staged_epw)
    host_stage = host_path_for_docker(stage)
    host_work = host_path_for_docker(work)
    args = [
        docker_bin(),
        "run",
        "--rm",
    ]
    user = energyplus_docker_user()
    if user:
        args.extend(["--user", user])
    args.extend(
        [
            "-v",
            f"{_win_mount(host_stage)}:/work/in",
            "-v",
            f"{_win_mount(host_work)}:/work/out",
            "-w",
            "/work/out",
            DOCKER_IMAGE,
            *cmd,
        ]
    )
    ensure_image(build=False)
    prog = Path(progress_dir) if progress_dir else None
    if prog is not None:
        return _run_docker_streaming(args, timeout=timeout, progress_dir=prog)
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
