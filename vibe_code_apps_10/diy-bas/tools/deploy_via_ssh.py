#!/usr/bin/env python3
"""
Portable diy-bas → Pi deploy (zip + scp + ssh), mirroring deploy_to_pi.ps1.
Use on Linux/macOS (or anywhere without robocopy). On Windows the GUI prefers deploy_to_pi.ps1.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

REMOTE_DATA_DIR = "/var/lib/diy-bas"
EXCLUDE_DIR_NAMES = frozenset({".venv", "__pycache__", ".git", "data", "staticfiles"})
EXCLUDE_FILE_NAMES = frozenset({".env"})
EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".sqlite3", ".db")


def _log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [deploy] {msg}", flush=True)


def _which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _should_skip(rel: Path) -> bool:
    for part in rel.parts:
        if part in EXCLUDE_DIR_NAMES:
            return True
    if rel.name in EXCLUDE_FILE_NAMES:
        return True
    for suf in EXCLUDE_SUFFIXES:
        if rel.name.endswith(suf):
            return True
    return False


def build_deploy_zip(project_dir: Path, zip_path: Path) -> int:
    """Write a zip of project_dir excluding secrets and bulky dirs. Returns byte size."""
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in project_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(project_dir)
            except ValueError:
                continue
            if _should_skip(rel):
                continue
            zf.write(path, rel.as_posix())
            count += 1
    size = zip_path.stat().st_size
    _log(f"Zipped {count} files → {zip_path} ({size} bytes)")
    return size


def _ssh(pi_user: str, pi_host: str, remote_bash: str, *, check: bool = True) -> int:
    r = subprocess.run(
        ["ssh", f"{pi_user}@{pi_host}", remote_bash],
        check=False,
    )
    if check and r.returncode != 0:
        raise SystemExit(f"ssh failed with exit code {r.returncode}")
    return int(r.returncode or 0)


def _scp(local: Path, pi_user: str, pi_host: str, remote_path: str) -> None:
    r = subprocess.run(["scp", str(local), f"{pi_user}@{pi_host}:{remote_path}"])
    if r.returncode != 0:
        raise SystemExit(f"scp failed with exit code {r.returncode}")


@dataclass
class DeployConfig:
    pi_host: str
    pi_user: str
    remote_dir: str = ""
    remote_bacnet_dir: str = ""
    run_bootstrap: bool = True
    start_app: bool = True
    use_docker_stack: bool = True
    test_login: bool = True
    sync_bootstrap_credentials_from_example: bool = True
    docker_maintenance: bool = True
    login_username: str = "integrator"
    login_password: str = "ChangeMeNow!123"
    verbose_deploy: bool = False
    bootstrap_log_tail: int = 80
    compose_log_tail: int = 50


def run_deploy(project_dir: Path, cfg: DeployConfig) -> None:
    import shlex

    if not _which("ssh") or not _which("scp"):
        raise SystemExit("Required commands not found: ssh and scp must be on PATH.")

    pi_host = cfg.pi_host.strip()
    pi_user = cfg.pi_user.strip()
    if not pi_host or not pi_user:
        raise SystemExit("Pi host and Pi user are required.")

    resolved_remote = cfg.remote_dir.strip() or f"/home/{pi_user}/diy-bas"
    resolved_bacnet = cfg.remote_bacnet_dir.strip() or f"/home/{pi_user}/diy-bacnet-server"
    remote_zip = f"/home/{pi_user}/diy-bas-deploy.zip"

    old_q = shlex.quote(resolved_remote)
    bak_q = shlex.quote(f"{resolved_remote}.bak")
    rz_q = shlex.quote(remote_zip)
    rd_q = shlex.quote(resolved_remote)
    rdd_q = shlex.quote(REMOTE_DATA_DIR)

    with tempfile.TemporaryDirectory(prefix="diy-bas-staging-") as tmp:
        zip_path = Path(tmp) / "diy-bas-deploy.zip"
        build_deploy_zip(project_dir, zip_path)
        _log(f"Uploading zip to {pi_user}@{pi_host}:{remote_zip} ...")
        _scp(zip_path, pi_user, pi_host, remote_zip)

    _log(f"Applying package on Pi (remote dir: {resolved_remote}) ...")
    rotate = (
        f"set -e; OLD={old_q}; BAK={bak_q}; "
        f'if [ -d "$OLD" ] && [ -f "$OLD/docker-compose.yml" ]; then (cd "$OLD" && docker compose down) 2>/dev/null || true; fi; '
        f'if [ -d "$BAK" ]; then sudo rm -rf "$BAK" 2>/dev/null || rm -rf "$BAK" || true; fi; '
        f'if [ -d "$OLD" ]; then mv "$OLD" "$BAK"; fi; mkdir -p "$OLD"'
    )
    _ssh(pi_user, pi_host, rotate)
    _ssh(
        pi_user,
        pi_host,
        f"sudo mkdir -p {rdd_q} && sudo chown -R {shlex.quote(pi_user)}:{shlex.quote(pi_user)} {rdd_q}",
    )
    unzip_exit = _ssh(
        pi_user,
        pi_host,
        f"unzip -q -o {rz_q} -d {rd_q}",
        check=False,
    )
    if unzip_exit == 1:
        _log("unzip exited 1 (warnings only); continuing.")
    elif unzip_exit != 0:
        raise SystemExit(f"remote unzip failed with exit code {unzip_exit}")

    _log("Normalizing line endings and permissions ...")
    _ssh(
        pi_user,
        pi_host,
        (
            f"find {rd_q} -type f -name '*.sh' -exec sed -i 's/\\r$//' {{}} + 2>/dev/null; "
            f"chmod +x {rd_q}/bootstrap_pi.sh {rd_q}/docker-entrypoint.sh {rd_q}/tools/pi_post_unzip_fix.sh 2>/dev/null || true"
        ),
        check=False,
    )
    _ssh(pi_user, pi_host, f"bash {rd_q}/tools/pi_post_unzip_fix.sh {rd_q} {shlex.quote(pi_user)}")

    if cfg.run_bootstrap:
        _log(f"Running bootstrap (last {cfg.bootstrap_log_tail} lines) ...")
        boot = (
            f"cd {rd_q} && export DIY_BACNET_SERVER_DIR={shlex.quote(resolved_bacnet)} && "
            f"BOOTSTRAP_NO_RUN=1 BOOTSTRAP_MANAGE_BACNET_SERVER=1 bash ./bootstrap_pi.sh 2>&1 | tail -n {int(cfg.bootstrap_log_tail)}"
        )
        _ssh(pi_user, pi_host, boot, check=False)

    if cfg.sync_bootstrap_credentials_from_example:
        _log("Merging bootstrap auth from .env.example into .env ...")
        _ssh(pi_user, pi_host, f"cd {rd_q} && python3 tools/sync_bootstrap_env_from_example.py", check=False)

    if cfg.start_app:
        compose_env = f"cd {rd_q} && export DIY_BACNET_SERVER_DIR={shlex.quote(resolved_bacnet)}"
        dq = "export DOCKER_CLI_HINTS=false"
        if cfg.use_docker_stack:
            _log(f"Docker: compose dir = {resolved_remote} ; DIY_BACNET_SERVER_DIR = {resolved_bacnet}")
            if cfg.verbose_deploy:
                _log("Verbose: docker compose build --progress=plain (diy-bas) ...")
                r = subprocess.run(
                    [
                        "ssh",
                        f"{pi_user}@{pi_host}",
                        f"{compose_env} && {dq} && docker compose build --progress=plain diy-bas",
                    ]
                )
                if r.returncode != 0:
                    subprocess.run(
                        ["ssh", f"{pi_user}@{pi_host}", f"{compose_env} && docker compose ps -a && ls -la bas/templates/bas 2>&1; id; groups"],
                        check=False,
                    )
                    raise SystemExit(f"docker compose build failed on Pi (exit {r.returncode}).")
                _log("Starting caddy + diy-bas (no rebuild) ...")
                subprocess.run(
                    ["ssh", f"{pi_user}@{pi_host}", f"{compose_env} && {dq} && docker compose up -d caddy diy-bas"],
                    check=True,
                )
            else:
                _log("Starting docker stack (compose up -d --build) ...")
                r = subprocess.run(
                    ["ssh", f"{pi_user}@{pi_host}", f"{compose_env} && {dq} && docker compose up -d --build caddy diy-bas"],
                )
                if r.returncode != 0:
                    subprocess.run(
                        [
                            "ssh",
                            f"{pi_user}@{pi_host}",
                            f"{compose_env} && docker compose ps -a 2>&1; echo '---'; ls -laR bas/templates 2>&1 | head -40",
                        ],
                        check=False,
                    )
                    raise SystemExit("docker compose up --build failed on Pi.")

        health_path = "http://127.0.0.1/api/health" if cfg.use_docker_stack else "http://127.0.0.1:5050/api/health"
        _log("Waiting for /api/health (up to ~44s) ...")
        healthy = False
        for i in range(22):
            r = subprocess.run(
                ["ssh", f"{pi_user}@{pi_host}", f"curl -s --max-time 2 {shlex.quote(health_path)}"],
                capture_output=True,
                text=True,
            )
            if r.returncode == 0 and (r.stdout or "").strip():
                healthy = True
                _log(f"Health OK (length {len(r.stdout)} chars).")
                break
            if i in (0, 5, 10):
                _log(f"Health poll {i} : ssh/curl exit={r.returncode} bodyLen={len(r.stdout or '')}")
            time.sleep(2)

        if cfg.use_docker_stack:
            _log("Recent docker compose logs (caddy, diy-bas) ...")
            subprocess.run(
                [
                    "ssh",
                    f"{pi_user}@{pi_host}",
                    f"cd {rd_q} && docker compose logs --no-color --tail={int(cfg.compose_log_tail)} caddy diy-bas",
                ],
                check=False,
            )

        if not healthy:
            subprocess.run(
                [
                    "ssh",
                    f"{pi_user}@{pi_host}",
                    f"cd {rd_q} && docker compose ps -a 2>&1; echo '---'; ls -la bas/templates/bas 2>&1; echo '---'; find bas -maxdepth 4 ! -readable 2>/dev/null | head -20",
                ],
                check=False,
            )
            raise SystemExit("App did not become healthy on Pi within timeout.")

        if cfg.test_login:
            login_url = "http://127.0.0.1/api/auth/login" if cfg.use_docker_stack else "http://127.0.0.1:5050/api/auth/login"
            _log(f"Verifying POST {login_url} ...")
            import json

            spec = json.dumps({"url": login_url, "username": cfg.login_username, "password": cfg.login_password})
            p = subprocess.Popen(
                ["ssh", f"{pi_user}@{pi_host}", f"cd {rd_q} && python3 tools/pi_verify_login.py"],
                stdin=subprocess.PIPE,
                text=True,
            )
            p.communicate(spec)
            if (p.returncode or 0) != 0:
                raise SystemExit("Login verification failed on Pi.")

    if cfg.docker_maintenance and cfg.start_app and cfg.use_docker_stack:
        _log("Docker maintenance: compose down in ~/diy-bas.bak* and prune ...")
        maint = (
            'set -e; shopt -s nullglob 2>/dev/null || true; for d in "$HOME"/diy-bas.bak*; do '
            'if [ -d "$d" ] && [ -f "$d/docker-compose.yml" ]; then (cd "$d" && docker compose down --remove-orphans) 2>/dev/null || true; fi; done; '
            "docker image prune -f >/dev/null 2>&1 || true"
        )
        _ssh(pi_user, pi_host, maint, check=False)

    _log("Done.")


def main() -> None:
    project_dir = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description="Deploy diy-bas to a Pi (zip + scp + ssh).")
    p.add_argument("--pi-host", required=True)
    p.add_argument("--pi-user", required=True)
    p.add_argument("--remote-dir", default="")
    p.add_argument("--remote-bacnet-dir", default="")
    p.add_argument("--no-run-bootstrap", action="store_true")
    p.add_argument("--no-start-app", action="store_true")
    p.add_argument("--no-docker-stack", action="store_true")
    p.add_argument("--no-test-login", action="store_true")
    p.add_argument("--no-sync-bootstrap-credentials", action="store_true")
    p.add_argument("--no-docker-maintenance", action="store_true")
    p.add_argument("--login-username", default="integrator")
    p.add_argument("--login-password", default="ChangeMeNow!123")
    p.add_argument("--verbose-deploy", action="store_true")
    p.add_argument("--bootstrap-log-tail", type=int, default=80)
    p.add_argument("--compose-log-tail", type=int, default=50)
    args = p.parse_args()
    cfg = DeployConfig(
        pi_host=args.pi_host,
        pi_user=args.pi_user,
        remote_dir=args.remote_dir,
        remote_bacnet_dir=args.remote_bacnet_dir,
        run_bootstrap=not args.no_run_bootstrap,
        start_app=not args.no_start_app,
        use_docker_stack=not args.no_docker_stack,
        test_login=not args.no_test_login,
        sync_bootstrap_credentials_from_example=not args.no_sync_bootstrap_credentials,
        docker_maintenance=not args.no_docker_maintenance,
        login_username=args.login_username,
        login_password=args.login_password,
        verbose_deploy=args.verbose_deploy,
        bootstrap_log_tail=args.bootstrap_log_tail,
        compose_log_tail=args.compose_log_tail,
    )
    run_deploy(project_dir, cfg)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
