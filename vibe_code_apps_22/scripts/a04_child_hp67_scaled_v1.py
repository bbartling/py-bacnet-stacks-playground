"""Build and score a04_child_hp67_scaled_v1 with compact scorecards (96-row continuity plant).

v1 is labeled PHYSICS_REPAIR_FAILED_NOT_RL_ELIGIBLE — not an RL-eligible physics champion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME, A04_SHA_ALLOWED, A04_SHA_LF
from eplus_gym.idf_diagnostics import count_w2a_objects
from eplus_gym.mega.child_model_ledger import bootstrap_ledger, register_child_model
from eplus_gym.mega.compact_scorecard import (
    PHYSICS_REPAIR_FAILED,
    build_compact_scorecard,
    idf_byte_and_lf_sha256,
    write_slim_artifacts,
)
from eplus_gym.mega.hp67_child_patch import child_sha256, patch_hp67_scaled_v1
from eplus_gym.mega.scored_day_runner import run_scored_continuity_day
from eplus_gym.site_env import require_site_root
from eplus_gym.site_pins import resolve_a04_and_epw

A04 = _APP / "models" / "eplus" / A04_IDF_NAME
CHILD_NAME = "a04_child_hp67_scaled_v1"
AUDIT_ROOT = _APP / "docs" / "audits" / "figures" / CHILD_NAME
DEFAULT_DAYS = (
    ("development_weekday", "2026-01-12"),
    ("development_weekend", "2026-01-25"),
    ("mild_weekday", "2026-03-16"),
)


def _assert_a04(raw: bytes) -> None:
    digest = hashlib.sha256(raw).hexdigest()
    lf = hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
    if digest not in A04_SHA_ALLOWED and lf != A04_SHA_LF:
        raise SystemExit("refusing to patch: A04 hash mismatch")


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def build_child_idf(*, force_rebuild: bool = False) -> tuple[Path, list[dict], str, bytes]:
    out_dir = _APP / "models" / "eplus" / "a04v2_candidates" / CHILD_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    out_idf = out_dir / "lakeside_w2a_hp67_scaled_v1.idf"
    manifest = AUDIT_ROOT / "patch_manifest.json"
    if out_idf.is_file() and not force_rebuild:
        text = out_idf.read_text(encoding="utf-8")
        patches: list[dict] = []
        if manifest.is_file():
            patches = json.loads(manifest.read_text(encoding="utf-8")).get("patches") or []
        child_bytes = text.encode("utf-8")
        return out_idf, patches, child_sha256(text), child_bytes
    raw = A04.read_bytes()
    _assert_a04(raw)
    try:
        text, patches = patch_hp67_scaled_v1(raw.decode("utf-8", errors="replace"))
    except ValueError as exc:
        if out_idf.is_file():
            text = out_idf.read_text(encoding="utf-8")
            patches = [{"op": "reuse_historical_v1", "note": str(exc)}]
            child_bytes = text.encode("utf-8")
            return out_idf, patches, child_sha256(text), child_bytes
        raise SystemExit(f"cannot build v1 child: {exc}") from exc
    out_idf.write_text(text, encoding="utf-8")
    child_bytes = text.encode("utf-8")
    return out_idf, patches, child_sha256(text), child_bytes


def score_day_continuity(
    *,
    site: Path,
    child_idf: Path,
    child_bytes: bytes,
    epw: Path,
    day: str,
    label: str,
) -> dict[str, object]:
    day_dir = AUDIT_ROOT / label
    live = run_scored_continuity_day(
        site_root=site,
        idf=child_idf,
        epw=epw,
        day=day,
        arm="incumbent",
        output=day_dir / "live_run",
    )
    byte_sha, lf_sha = idf_byte_and_lf_sha256(child_bytes)
    gate = dict(live.get("gate") or {})
    rc = 0 if gate.get("completed_successfully") else 1
    scorecard = build_compact_scorecard(
        label=label,
        day=day,
        arm="incumbent",
        child_name=CHILD_NAME,
        child_idf_byte_sha256=byte_sha,
        child_idf_lf_normalized_sha256=lf_sha,
        gate=gate,
        returncode=rc,
        payload=live.get("payload"),
        physics_status=PHYSICS_REPAIR_FAILED,
        rl_eligible=False,
    )
    write_slim_artifacts(day_dir, scorecard)
    return scorecard


def main() -> int:
    p = argparse.ArgumentParser(description=f"Build and score {CHILD_NAME} (failed physics repair v1)")
    p.add_argument("--site-root", default="")
    p.add_argument("--build-only", action="store_true")
    p.add_argument("--force-rebuild", action="store_true")
    args = p.parse_args()

    child_idf, patches, idf_sha, child_bytes = build_child_idf(force_rebuild=bool(args.force_rebuild))
    byte_sha, lf_sha = idf_byte_and_lf_sha256(child_bytes)
    parent_sha = hashlib.sha256(A04.read_bytes()).hexdigest()
    ledger = bootstrap_ledger(A04)
    register_child_model(
        ledger,
        child_name=CHILD_NAME,
        child_idf_path=child_idf,
        patches=patches,
        rationale="Per-zone capacity+airflow+water scaled by 67-HP BAS split (v1 — physics repair failed).",
    )
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    _write(AUDIT_ROOT / "child_model_ledger.json", ledger.to_dict())
    _write(
        AUDIT_ROOT / "patch_manifest.json",
        {
            "child_name": CHILD_NAME,
            "parent_idf": A04_IDF_NAME,
            "parent_sha256": parent_sha,
            "child_idf_sha256": idf_sha,
            "child_idf_byte_sha256": byte_sha,
            "child_idf_lf_normalized_sha256": lf_sha,
            "child_idf_path": str(child_idf.relative_to(_APP)).replace("\\", "/"),
            "physics_status": PHYSICS_REPAIR_FAILED,
            "object_counts": count_w2a_objects(child_idf.read_text(encoding="utf-8", errors="replace")),
            "patches": patches,
        },
    )
    if args.build_only:
        print(json.dumps({"child_idf_sha256": idf_sha, "build_only": True}, indent=2))
        return 0

    site = require_site_root(args.site_root or None)
    _idf, epw = resolve_a04_and_epw(site)
    pinned = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    if pinned.is_file():
        epw = pinned

    day_results = []
    for label, day in DEFAULT_DAYS:
        day_results.append(
            score_day_continuity(
                site=site,
                child_idf=child_idf,
                child_bytes=child_bytes,
                epw=epw,
                day=day,
                label=label,
            )
        )

    summary = {
        "schema": "vibe22.a04_child_hp67_scaled_v1.v2",
        "child_name": CHILD_NAME,
        "physics_status": PHYSICS_REPAIR_FAILED,
        "rl_eligible": False,
        "child_idf_sha256": idf_sha,
        "child_idf_byte_sha256": byte_sha,
        "child_idf_lf_normalized_sha256": lf_sha,
        "parent_sha256": parent_sha,
        "days": day_results,
        "bacnet_command_authority": 0,
        "vibe19_untouched": True,
        "claim_labels": [
            "PHYSICS_REPAIR_FAILED_NOT_RL_ELIGIBLE",
            "SIMULATION_ONLY_RL_RESEARCH",
            "NO_BACNET_COMMAND_AUTHORITY",
        ],
    }
    _write(AUDIT_ROOT / "campaign_summary.json", summary)
    print(json.dumps({"physics_status": PHYSICS_REPAIR_FAILED, "days_run": len(day_results)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
