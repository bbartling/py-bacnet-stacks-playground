"""Machine-readable experiment ledger. Fail closed on missing gate artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

A04_SHA256 = "212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683"
PINNED_GATES = 5
HISTORICAL_PPO = 488
HISTORICAL_DQN = 488


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_experiment_ledger(
    *,
    app_root: Path,
    a04_idf: Path | None = None,
    train_jsonl: Path | None = None,
    eval_csv: Path | None = None,
) -> dict[str, Any]:
    app_root = Path(app_root)
    gates_path = app_root / "docs" / "audits" / "figures" / "postfix" / "p1_gates.json"
    if not gates_path.is_file():
        raise FileNotFoundError(f"missing post-fix gates artifact {gates_path}")
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    smoke = list(gates.get("smoke") or [])
    pair = dict(gates.get("pair") or {})
    n_gates = len(smoke) + (2 if pair else 0)
    if n_gates != PINNED_GATES:
        raise ValueError(f"expected {PINNED_GATES} post-fix gate calls, found {n_gates}")
    if not pair.get("physics_moved"):
        raise ValueError("Jan 26 pair physics_moved is not true")

    a04_sha = None
    if a04_idf and Path(a04_idf).is_file():
        a04_sha = _sha256_file(Path(a04_idf))
        if a04_sha != A04_SHA256:
            raise ValueError(f"A04 sha {a04_sha} != pin {A04_SHA256}")

    valid_train = 0
    if train_jsonl and Path(train_jsonl).is_file():
        # Post-fix train jsonl would count; year2xsyn is never passed here.
        valid_train = sum(1 for _ in Path(train_jsonl).read_text(encoding="utf-8").splitlines() if _.strip())

    valid_eval = 0
    if eval_csv and Path(eval_csv).is_file():
        lines = Path(eval_csv).read_text(encoding="utf-8").splitlines()
        valid_eval = max(0, len(lines) - 1)

    body = {
        "schema": "vibe22.experiment_ledger.v1",
        "a04_sha256_pin": A04_SHA256,
        "a04_sha256_verified": a04_sha,
        "calibration_scope": "monthly_partial_period_guideline_14_screen",
        "valid_postfix_training_episodes": int(valid_train),
        "historical_invalid_training_episodes": {
            "PPO": HISTORICAL_PPO,
            "DQN": HISTORICAL_DQN,
            "run_id": "year2xsyn",
            "exclusion": "INVALID_PRE_FIX_EPLUS_SEVERE",
        },
        "valid_postfix_eplus_gate_calls": n_gates,
        "gate_days": [r.get("day") for r in smoke],
        "jan26_pair": {
            "kind": "manual_control_perturbation",
            "not_rl_policy": True,
            "incumbent_peak_kw": pair.get("incumbent_peak"),
            "perturbed_peak_kw": pair.get("perturbed_peak"),
            "incumbent_kwh": pair.get("incumbent_kwh"),
            "perturbed_kwh": pair.get("perturbed_kwh"),
        },
        "deterministic_validation_episodes": int(valid_eval),
        "heldout_test_episodes": 0,
        "january_status": (
            "not_pristine_untouched_holdout; calibration and P1 used 2026-01-26; "
            "chronology may still be used for future model selection; no new final test window designated"
        ),
        "excluded": [
            {
                "run_id": "year2xsyn",
                "reason": "INVALID_PRE_FIX_EPLUS_SEVERE — TRAIN EXPLORATION ONLY; not a learning result",
            },
            {
                "kind": "train_reward_json_as_eval",
                "reason": "last train reward.json is not deterministic evaluation",
            },
        ],
        "p1_gates_path": str(gates_path.as_posix()),
    }
    blob = json.dumps({k: body[k] for k in body if k != "sha256"}, sort_keys=True).encode("utf-8")
    body["sha256"] = hashlib.sha256(blob).hexdigest()
    return body


def write_experiment_ledger(path: Path, ledger: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return path
