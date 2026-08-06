"""Minimal lean CLI regen: real held-out recursive cards, no provisional notes."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

os.environ.setdefault(
    "LAKESIDE_SITE_ROOT",
    r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
)
os.environ["VIBE22_ALLOW_CLI_TRAIN"] = "1"

from chrono_splits import build_split_manifest, write_manifest  # noqa: E402
from train_eplus_delta_15min import (  # noqa: E402
    export_delta_artifacts,
    lean_train_delta,
    load_paired_and_build_delta,
)
from train_real_baseline_15min import (  # noqa: E402
    export_real_baseline_artifacts,
    lean_bake_off,
    load_real_baseline_frame,
)

OUT = ROOT / "ml" / "artifacts"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    print("=== A: real baseline lean + chrono splits ===", flush=True)
    train_df = load_real_baseline_frame(winter_only=True, max_days=36)
    print("rows", len(train_df), "days", train_df["day"].nunique(), flush=True)
    manifest = build_split_manifest(train_df)
    write_manifest(OUT / "eval" / "split_manifest.json", manifest)
    base = lean_bake_off(train_df, n_splits=3, split_manifest=manifest, out_dir=OUT)
    base_paths = export_real_baseline_artifacts(base, OUT)
    base_card = json.loads(base_paths["card"].read_text(encoding="utf-8"))
    assert "provisional" not in json.dumps(base_card.get("cv_recursive_96_heldout", {})).lower()
    print("baseline champion", base_card["champion"], flush=True)

    print("=== B: eplus delta lean ===", flush=True)
    from artifact_paths import artifact_paths

    paired = artifact_paths()["eplus_paired"]
    delta_df, paired_path = load_paired_and_build_delta(paired, out_dir=OUT)
    delta = lean_train_delta(delta_df, n_splits=3)
    delta_paths = export_delta_artifacts(delta, OUT, paired_source=str(paired_path))
    delta_card = json.loads(delta_paths["card"].read_text(encoding="utf-8"))
    assert "provisional" not in json.dumps(delta_card.get("cv_recursive_96_heldout", {})).lower()
    print("delta champion", delta_card["champion"], "n_days", delta_card.get("n_days"), flush=True)
    print(json.dumps({"base": str(base_paths["card"]), "delta": str(delta_paths["card"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
