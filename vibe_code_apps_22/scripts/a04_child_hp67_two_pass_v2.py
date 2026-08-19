"""hp67 v2 two-pass sizing: Autosize Pass 1 → EIO hard-size Pass 2 → optional staged banks."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME, A04_SHA_ALLOWED, A04_SHA_LF
from eplus_gym.energyplus_cli import run_energyplus_cli
from eplus_gym.epw_stage import stage_year_aware_epw
from eplus_gym.idf_diagnostics import count_w2a_objects
from eplus_gym.mega.child_model_ledger import bootstrap_ledger, register_child_model
from eplus_gym.mega.compact_scorecard import (
    PHYSICS_REPAIR_FAILED,
    build_compact_scorecard,
    idf_byte_and_lf_sha256,
    write_slim_artifacts,
)
from eplus_gym.mega.hp67_banks import build_hp67_banks_child
from eplus_gym.mega.hp67_two_pass import CAPACITY_MULT, child_sha256, patch_pass1_autosize, patch_pass2_hardsize
from eplus_gym.mega.scored_day_runner import run_scored_continuity_day
from eplus_gym.site_env import require_site_root
from eplus_gym.site_pins import resolve_a04_and_epw
from eplus_gym.stage_idf import stage_idf_for_period
from eplus_gym.trackb_banks import scored_runtime_w2a_pass

A04 = _APP / "models" / "eplus" / A04_IDF_NAME
CHILD_NAME = "a04_child_hp67_two_pass_v2"
AUDIT_ROOT = _APP / "docs" / "audits" / "figures" / "a04_child_hp67_scaled_v2"
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


def run_pass1_sizing(
    *,
    site: Path,
    epw: Path,
    sensitivity: str,
    out: Path,
    begin: str,
    end: str,
) -> tuple[str, str, dict]:
    raw = A04.read_bytes()
    _assert_a04(raw)
    pass1_text, pass1_patches = patch_pass1_autosize(
        raw.decode("utf-8", errors="replace"),
        sensitivity=sensitivity,  # type: ignore[arg-type]
    )
    pass1_dir = out / "pass1_sizing"
    pass1_dir.mkdir(parents=True, exist_ok=True)
    sizing_idf = pass1_dir / "pass1_autosize.idf"
    sizing_idf.write_text(pass1_text, encoding="utf-8")
    staged = stage_idf_for_period(
        sizing_idf,
        pass1_dir / "staged.idf",
        begin,
        end,
        six_zone_actuators=False,
        disable_sizing=False,
    )
    staged_epw_meta = stage_year_aware_epw(epw, pass1_dir / f"staged_{epw.name}")
    staged_epw = Path(staged_epw_meta["staged_epw"])
    r1 = run_energyplus_cli(idf=staged, epw=staged_epw, output=pass1_dir / "eplus_out")
    eio = pass1_dir / "eplus_out" / "eplusout.eio"
    if not eio.is_file():
        hits = list((pass1_dir / "eplus_out").rglob("eplusout.eio"))
        eio = hits[0] if hits else eio
    if not eio.is_file():
        raise SystemExit("pass 1 did not write eplusout.eio")
    eio_text = eio.read_text(encoding="utf-8", errors="replace")
    _write(
        pass1_dir / "pass1_manifest.json",
        {
            "returncode": r1.get("returncode"),
            "capacity_sensitivity": sensitivity,
            "capacity_mult": CAPACITY_MULT[sensitivity],  # type: ignore[index]
            "assumption": "67-HP inventory × 3-ton nominal unless field-proven",
            "patches": pass1_patches,
        },
    )
    return pass1_text, eio_text, {"returncode": r1.get("returncode"), "eio_path": str(eio)}


def build_pass2_child(
    pass1_text: str,
    eio_text: str,
    *,
    sensitivity: str,
    use_banks: bool,
) -> tuple[Path, list[dict], str, bytes, dict]:
    if use_banks:
        expanded, banks_meta = build_hp67_banks_child(
            pass1_text,
            eio_text=eio_text,
            sensitivity=sensitivity,
        )
        pass2_patches = [{"op": "banks_fallback", **banks_meta}]
        text = expanded
    else:
        text, pass2_patches = patch_pass2_hardsize(
            pass1_text,
            eio_text=eio_text,
            sensitivity=sensitivity,  # type: ignore[arg-type]
        )
    out_dir = _APP / "models" / "eplus" / "a04v2_candidates" / CHILD_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "banks" if use_banks else "hardsize"
    out_idf = out_dir / f"lakeside_w2a_hp67_v2_{suffix}.idf"
    out_idf.write_text(text, encoding="utf-8")
    child_bytes = text.encode("utf-8")
    return out_idf, pass2_patches, child_sha256(text), child_bytes, {"use_banks": use_banks}


def score_days(
    *,
    site: Path,
    child_idf: Path,
    child_bytes: bytes,
    epw: Path,
    physics_status: str,
    rl_eligible: bool,
) -> list[dict]:
    byte_sha, lf_sha = idf_byte_and_lf_sha256(child_bytes)
    results = []
    for label, day in DEFAULT_DAYS:
        day_dir = AUDIT_ROOT / label
        live = run_scored_continuity_day(
            site_root=site,
            idf=child_idf,
            epw=epw,
            day=day,
            arm="incumbent",
            output=day_dir / "live_run",
        )
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
            physics_status=physics_status,
            rl_eligible=rl_eligible,
        )
        write_slim_artifacts(day_dir, scorecard)
        results.append(scorecard)
    return results


def main() -> int:
    p = argparse.ArgumentParser(description=f"Build and score {CHILD_NAME}")
    p.add_argument("--site-root", default="")
    p.add_argument("--sensitivity", choices=("low", "base", "high"), default="base")
    p.add_argument("--build-only", action="store_true")
    p.add_argument("--use-banks", action="store_true", help="Force staged HP banks (Track B pattern)")
    p.add_argument("--no-auto-banks-on-w2a-fail", action="store_true")
    p.add_argument("--begin", default="2026-01-12")
    p.add_argument("--end", default="2026-01-12")
    args = p.parse_args()

    site = require_site_root(args.site_root or None)
    _idf, epw = resolve_a04_and_epw(site)
    pinned = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    if pinned.is_file():
        epw = pinned

    out = AUDIT_ROOT / f"sensitivity_{args.sensitivity}"
    pass1_text, eio_text, pass1_meta = run_pass1_sizing(
        site=site,
        epw=epw,
        sensitivity=args.sensitivity,
        out=out,
        begin=str(args.begin)[:10],
        end=str(args.end)[:10],
    )

    use_banks = bool(args.use_banks)
    child_idf, patches, idf_sha, child_bytes, build_meta = build_pass2_child(
        pass1_text,
        eio_text,
        sensitivity=args.sensitivity,
        use_banks=use_banks,
    )
    byte_sha, lf_sha = idf_byte_and_lf_sha256(child_bytes)
    parent_sha = hashlib.sha256(A04.read_bytes()).hexdigest()
    ledger = bootstrap_ledger(A04)
    register_child_model(
        ledger,
        child_name=CHILD_NAME,
        child_idf_path=child_idf,
        patches=patches,
        rationale="hp67 v2 two-pass EIO hard-sizing (no water=air*0.05 fallback).",
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
            "pass1": pass1_meta,
            "pass2": build_meta,
            "capacity_sensitivity": args.sensitivity,
            "object_counts": count_w2a_objects(child_idf.read_text(encoding="utf-8", errors="replace")),
            "patches": patches,
        },
    )
    if args.build_only:
        print(json.dumps({"child_idf_sha256": idf_sha, "build_only": True}, indent=2))
        return 0

    day_results = score_days(
        site=site,
        child_idf=child_idf,
        child_bytes=child_bytes,
        epw=epw,
        physics_status=PHYSICS_REPAIR_FAILED,
        rl_eligible=False,
    )
    w2a_ok = all(
        scored_runtime_w2a_pass({"w2a_low_airflow_by_phase": d.get("w2a_low_airflow_by_phase") or {}})
        for d in day_results
    )
    if not args.no_auto_banks_on_w2a_fail and not w2a_ok and not use_banks:
        banks_idf, banks_patches, banks_sha, banks_bytes, banks_meta = build_pass2_child(
            pass1_text,
            eio_text,
            sensitivity=args.sensitivity,
            use_banks=True,
        )
        _write(AUDIT_ROOT / "banks_fallback_manifest.json", banks_meta)
        day_results = score_days(
            site=site,
            child_idf=banks_idf,
            child_bytes=banks_bytes,
            epw=epw,
            physics_status=PHYSICS_REPAIR_FAILED,
            rl_eligible=False,
        )
        child_idf, patches, idf_sha, child_bytes = banks_idf, banks_patches, banks_sha, banks_bytes
        w2a_ok = all(
            scored_runtime_w2a_pass({"w2a_low_airflow_by_phase": d.get("w2a_low_airflow_by_phase") or {}})
            for d in day_results
        )

    physics_status = PHYSICS_REPAIR_FAILED if not w2a_ok else "PHYSICS_REPAIR_CANDIDATE"
    summary = {
        "schema": "vibe22.a04_child_hp67_two_pass_v2.v1",
        "child_name": CHILD_NAME,
        "physics_status": physics_status,
        "rl_eligible": w2a_ok,
        "child_idf_sha256": idf_sha,
        "child_idf_byte_sha256": byte_sha,
        "child_idf_lf_normalized_sha256": lf_sha,
        "capacity_sensitivity": args.sensitivity,
        "days": day_results,
        "w2a_scored_runtime_pass": w2a_ok,
        "bacnet_command_authority": 0,
        "claim_labels": [
            physics_status,
            "NO_BACNET_COMMAND_AUTHORITY",
            "NO_PRISTINE_LOCKED_TEST_AVAILABLE",
        ],
    }
    _write(AUDIT_ROOT / "campaign_summary.json", summary)
    print(json.dumps({"physics_status": physics_status, "w2a_ok": w2a_ok}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
