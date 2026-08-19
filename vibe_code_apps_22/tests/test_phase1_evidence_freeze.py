from __future__ import annotations

import json
from pathlib import Path

from eplus_gym.date_use_ledger import NO_LOCKED_UNSEEN
from eplus_gym.phase1_evidence_freeze import (
    NO_PRISTINE_LOCKED_TEST,
    audit_research_long_run,
    build_frozen_date_use_ledger,
    build_phase1_evidence_freeze,
)


def test_date_ledger_records_no_pristine_locked_test():
    ledger = build_frozen_date_use_ledger()
    assert ledger["locked_test"]["status"] == NO_PRISTINE_LOCKED_TEST
    assert ledger["locked_unseen_label"] == NO_LOCKED_UNSEEN
    assert "2026-01-26" in ledger["physics_development"]["dates"]
    assert ledger["ledger_sha256"]


def test_research_long_audit_from_fixture(tmp_path: Path) -> None:
    run = tmp_path / "research_long_fixture"
    run.mkdir()
    rows = [
        {
            "arm": "incumbent",
            "day": "2025-12-15",
            "training_reward": -1.0,
            "peak_kw": 100.0,
            "daily_kwh": 1000.0,
            "readiness_ok": False,
            "decoded_schedule_fingerprint": "abc",
        },
        {
            "arm": "trained_dqn_seed0",
            "day": "2025-12-15",
            "training_reward": 0.5,
            "peak_kw": 90.0,
            "daily_kwh": 900.0,
            "readiness_ok": True,
            "decoded_schedule_fingerprint": "def",
        },
    ]
    (run / "eval.json").write_text(
        json.dumps(
            {
                "schema": "vibe22.research_long_eval.v1",
                "days": ["2025-12-15"],
                "rows": rows,
                "winner": "trained_dqn_seed0",
                "winner_rule": "test",
                "locked_unseen": NO_LOCKED_UNSEEN,
            }
        ),
        encoding="utf-8",
    )
    (run / "ppo_seed0").mkdir()
    (run / "ppo_seed0" / "train_summary.json").write_text(
        json.dumps({"n_episodes_logged": 3, "timesteps": 3}), encoding="utf-8"
    )
    audit = audit_research_long_run(run)
    assert audit["evaluation_rows"] == 2
    assert audit["winner_legacy_key"] == "trained_dqn_seed0"
    assert audit["validation_selected_policy"] is None  # baselines incomplete


def test_phase1_freeze_is_deterministic_except_timestamps(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "eval.json").write_text(
        json.dumps({"days": [], "rows": [], "winner": None, "winner_rule": "x"}),
        encoding="utf-8",
    )
    a = build_phase1_evidence_freeze(research_long_run_root=run)
    b = build_phase1_evidence_freeze(research_long_run_root=run)
    for k in ("frozen_at_utc", "freeze_sha256"):
        a.pop(k, None)
        b.pop(k, None)
    a["date_use_ledger"].pop("frozen_at_utc", None)
    a["date_use_ledger"].pop("ledger_sha256", None)
    b["date_use_ledger"].pop("frozen_at_utc", None)
    b["date_use_ledger"].pop("ledger_sha256", None)
    assert a == b
