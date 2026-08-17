"""Build a Track B bank plan + autosized A04 child metadata. Never overwrite A04."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME, A04_SHA_ALLOWED, A04_SHA_CRLF, A04_SHA_LF
from eplus_gym.idf_objects import find_named_object, iter_objects
from eplus_gym.trackb_banks import (
    HTG_TYPE,
    PUBLIC_LABEL,
    champion_gates_template,
    clone_heating_coil_banks,
    nine_zone_plan,
    six_group_plan,
)
from eplus_native.idf_inspect import NINE_ZONES

A04 = _APP / "models" / "eplus" / A04_IDF_NAME


def _assert_a04(raw: bytes) -> None:
    d = hashlib.sha256(raw).hexdigest()
    lf = hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
    if d not in A04_SHA_ALLOWED and lf != A04_SHA_LF:
        raise SystemExit("refusing to patch: A04 hash mismatch")


def expand_autosize_banks(src: str, plan: dict) -> str:
    """Replace each zone heating coil with multiple Autosize EquationFit banks."""
    out = src
    by_zone = {row["eplus_zone"]: row for row in plan["zones"]}
    for z in NINE_ZONES:
        name = f"{z} WAHP Heating Coil"
        block = find_named_object(out, HTG_TYPE, name)
        if not block:
            raise SystemExit(f"missing heating coil for {z}")
        n_banks = int(by_zone[z]["n_banks"])
        clones = clone_heating_coil_banks(block, n_banks=n_banks, zone=z)
        out = out.replace(block, "\n\n".join(clones), 1)
    n = len(iter_objects(out, HTG_TYPE))
    if n <= 9:
        raise SystemExit(f"expected more than 9 heating coils after bank expand, found {n}")
    return out


def build_trackb_plan(*, sensitivity: str, run_id: str) -> dict:
    if run_id in {A04_IDF_NAME, Path(A04_IDF_NAME).stem}:
        raise SystemExit("refusing to overwrite A04")
    raw = A04.read_bytes()
    _assert_a04(raw)
    nine = nine_zone_plan(sensitivity=sensitivity)
    six = six_group_plan(sensitivity=sensitivity)
    text = raw.decode("utf-8", errors="replace")
    expanded = expand_autosize_banks(text, nine)
    out_dir = _APP / "models" / "eplus" / "a04v2_candidates" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_idf = out_dir / f"lakeside_w2a_trackb_{run_id}.idf"
    data = expanded.encode("utf-8")
    out_idf.write_bytes(data)
    meta = {
        "schema": "vibe22.trackb.candidate.v1",
        "run_id": run_id,
        "public_label": PUBLIC_LABEL,
        "as_built": False,
        "assumes_identical_3ton": False,
        "parent_model": A04_IDF_NAME,
        "parent_sha256": A04_SHA_CRLF,
        "idf": out_idf.name,
        "idf_sha256": hashlib.sha256(data).hexdigest(),
        "n_heating_coils": len(iter_objects(expanded, HTG_TYPE)),
        "sensitivity": sensitivity,
        "six_group_plan": six,
        "nine_zone_plan": nine,
        "champion_gates": champion_gates_template(),
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
    print(json.dumps({k: meta[k] for k in ("run_id", "idf", "n_heating_coils", "public_label", "idf_sha256")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
