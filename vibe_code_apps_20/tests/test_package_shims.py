"""Back-compat contract: old flat-module paths keep working for vibe19 sidecar."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_old_flat_imports_still_work():
    import calibrate
    import config
    import easy_button
    import ep_docker
    import ep_mcp_client
    import results_parse
    import run_manifest
    import vibe19_bridge
    import wattlab_defaults
    import weather_epw
    from ecm_library.measure_sets import expand_measure_set, list_measure_sets
    from idf_patches import apply_run_period
    from idf_patches.schedules import apply_fan_avail_continuous

    assert callable(wattlab_defaults.resolve_profile)
    assert callable(easy_button.main)
    assert callable(calibrate.main)
    assert callable(vibe19_bridge.main)
    assert callable(weather_epw.main)
    assert callable(apply_run_period)
    assert callable(apply_fan_avail_continuous)
    assert callable(expand_measure_set) and callable(list_measure_sets)
    assert config.ROOT == ROOT
    assert callable(ep_docker.docker_bin)
    assert callable(ep_mcp_client.simulate)
    assert callable(results_parse.file_sha256)
    assert callable(run_manifest.build_run_manifest)


def test_shim_scripts_run_as_subprocess():
    """vibe19 sidecar contract: `python easy_button.py --help` etc. from vibe20 dir."""
    import os

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}  # help text has arrows; cp1252 chokes
    for script in ("easy_button.py", "calibrate.py", "vibe19_bridge.py", "wattlab_defaults.py"):
        proc = subprocess.run(
            [sys.executable, script, "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        assert proc.returncode == 0, f"{script} --help failed: {proc.stderr[-1000:]}"


def test_wattlab_cli_help():
    import os

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "wattlab.cli", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    for cmd in ("twin", "easy-button", "calibrate", "bridge", "bench", "crosscheck", "studio", "defaults"):
        assert cmd in proc.stdout
