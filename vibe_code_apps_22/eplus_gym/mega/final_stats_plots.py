"""Phase 16: final stats/plots manifest for Phase 0 publisher consumption."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from eplus_gym.mega._json import sha256_obj

SCHEMA = "vibe22.mega.final_stats_plots.v1"
REQUIRED_FINAL_PLOTS = (
    "paired_diff_bootstrap_ci",
    "seed_variability_box",
    "pareto_cost_peak",
    "strategy_cost_comparison",
)


def build_final_plot_manifest(
    *,
    source_manifest_paths: Sequence[str],
    paired_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "publisher": "phase0_plot_publisher",
        "required_plot_ids": list(REQUIRED_FINAL_PLOTS),
        "source_manifests": list(source_manifest_paths),
        "paired_stats": paired_stats or {},
        "consumes_phase0_allowlist": True,
    }
    body["manifest_sha256"] = sha256_obj(body)
    return body


def write_final_plot_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
