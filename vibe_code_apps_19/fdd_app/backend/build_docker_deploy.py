#!/usr/bin/env python3
"""
Build client deploy artifacts (read-only site/ + optional Docker image).

Workflow:
  1. Tune charts locally: DASHBOARD_MODE=full python app.py
  2. python build_docker_deploy.py --from-session
  3. docker build -f ../Dockerfile.deploy -t open-fdd-vibe-coder:deploy ..
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from package_dashboard import build_readonly_package

ROOT = Path(__file__).resolve().parent
APP19 = ROOT.parent
SITE_DIR = ROOT / "site"


def build_deploy_site(*, from_session: bool = True) -> dict:
    result = build_readonly_package(
        out_dir=SITE_DIR,
        zip_path=ROOT / "dashboard_readonly.zip",
        from_session=from_session,
    )
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build read-only site/ for Docker deploy image")
    parser.add_argument("--from-session", action="store_true", default=True)
    parser.add_argument("--no-session", action="store_true", help="Use default params, no saved notes")
    parser.add_argument("--docker", action="store_true", help="Run docker build for Dockerfile.deploy")
    args = parser.parse_args()
    from_session = not args.no_session

    result = build_deploy_site(from_session=from_session)
    print(f"Site build: {result.get('site_dir', SITE_DIR)}")
    print(f"Zip:        {result.get('zip_path', ROOT / 'dashboard_readonly.zip')}")

    if args.docker:
        cmd = [
            "docker",
            "build",
            "-f",
            str(APP19 / "Dockerfile.deploy"),
            "-t",
            "open-fdd-vibe-coder:deploy",
            str(APP19),
        ]
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd)

    print("See DEPLOY.md for docker run examples.")


if __name__ == "__main__":
    main()
