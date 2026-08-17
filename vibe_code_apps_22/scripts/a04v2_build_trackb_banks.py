"""Build a Track B bank plan + complete A04 child IDF. Never overwrite A04."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME, A04_SHA_ALLOWED, A04_SHA_CRLF, A04_SHA_LF
from eplus_gym.idf_objects import iter_objects
from eplus_gym.trackb_banks import (
    HTG_TYPE,
    PUBLIC_LABEL,
    ZONEHVAC_TYPE,
    assert_reference_integrity,
    champion_gates_template,
    expand_complete_banks,
    nine_zone_plan,
    six_group_plan,
    structural_fixture_totals,
)

A04 = _APP / "models" / "eplus" / A04_IDF_NAME


def _assert_a04(raw: bytes) -> None:
    d = hashlib.sha256(raw).hexdigest()
    lf = hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
    if d not in A04_SHA_ALLOWED and lf != A04_SHA_LF:
        raise SystemExit("refusing to patch: A04 hash mismatch")


def expand_autosize_banks(src: str, plan: dict, *, sizing_totals: dict | None = None) -> str:
    totals = sizing_totals or structural_fixture_totals(src)
    return expand_complete_banks(src, plan, sizing_totals=totals)


def build_trackb_plan(*, sensitivity: str, run_id: str, sizing_totals: dict | None = None) -> dict:
    if run_id in {A04_IDF_NAME, Path(A04_IDF_NAME).stem}:
        raise SystemExit("refusing to overwrite A04")
    raw = A04.read_bytes()
    _assert_a04(raw)
    nine = nine_zone_plan(sensitivity=sensitivity)
    six = six_group_plan(sensitivity=sensitivity)
    text = raw.decode("utf-8", errors="replace")
    expanded = expand_autosize_banks(text, nine, sizing_totals=sizing_totals)
    integrity = assert_reference_integrity(expanded, nine)
    out_dir = _APP / "models" / "eplus" / "a04v2_candidates" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_idf = out_dir / f"lakeside_w2a_trackb_{run_id}.idf"
    data = expanded.encode("utf-8")
    out_idf.write_bytes(data)
    meta = {
        "schema": "vibe22.trackb.candidate.v2",
        "run_id": run_id,
        "public_label": PUBLIC_LABEL,
        "as_built": False,
        "assumes_identical_3ton": False,
        "parent_model": A04_IDF_NAME,
        "parent_sha256": A04_SHA_CRLF,
        "idf": out_idf.name,
        "idf_sha256": hashlib.sha256(data).hexdigest(),
        "n_heating_coils": len(iter_objects(expanded, HTG_TYPE)),
        "n_zonehvac": len(iter_objects(expanded, ZONEHVAC_TYPE)),
        "sensitivity": sensitivity,
        "six_group_plan": six,
        "nine_zone_plan": nine,
        "reference_integrity": integrity,
        "sizing_totals_provenance": (next(iter((sizing_totals or structural_fixture_totals(text)).values())).get("provenance")),
        "champion_gates": champion_gates_template(),
        "track_b_builder_prototype_created": True,
        "track_b_structural_validation_passed": True,
        "track_b_live_energyplus_executed": False,
        "track_b_completed": False,
    }
    (out_dir / "parameters.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (out_dir / "bank_plan.json").write_text(json.dumps(six, indent=2) + "\n", encoding="utf-8")
    return meta


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sensitivity", default="base", choices=("low", "base", "high"))
    p.add_argument("--run-id", default="trackb_banks_base")
    p.add_argument("--write-idf", action="store_true", help="write generated IDF (gitignored)")
    args = p.parse_args()
    if not args.write_idf:
        six = six_group_plan(sensitivity=args.sensitivity)
        print(json.dumps({"public_label": PUBLIC_LABEL, "plan": six}, indent=2))
        return 0
    meta = build_trackb_plan(sensitivity=args.sensitivity, run_id=args.run_id)
    keys = (
        "run_id",
        "idf",
        "n_heating_coils",
        "n_zonehvac",
        "public_label",
        "idf_sha256",
        "track_b_structural_validation_passed",
    )
    print(json.dumps({k: meta[k] for k in keys}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
