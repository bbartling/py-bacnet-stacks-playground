"""Derive Vibe22 RL PoC publication packs from finished research-long artifacts.

Never rewrites historical campaign manifests. Never trains. Never launches EnergyPlus.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

HONESTY_LABELS = [
    "SIMULATION-ONLY RL RESEARCH",
    "NOT VALIDATED FOR OPERATIONAL DSM",
    "NO PRISTINE LOCKED TEST",
    "A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION",
    "TOU TARIFF IS ILLUSTRATIVE",
    "CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2",
    "NO BACNET COMMAND AUTHORITY",
]

DEC_FLOOR_DISCLOSURE = (
    "Validation demand-cost accounting initialized the December billing floor at "
    "zero and may overstate incremental candidate demand charges."
)

PRIMARY_RUN = "research_long_flat_plus_demand_20260820T132506Z"
SECONDARY_RUN = "research_long_illustrative_tou_plus_demand_20260820T210304Z"

REPRESENTATIVE_DAY = "2025-12-15"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def school_occupied_from_row(row: dict[str, Any]) -> bool:
    proof = row.get("schedule_proof") or {}
    win = proof.get("school_occupancy_window") or {}
    if "school_occupied" in win:
        return bool(win["school_occupied"])
    # Fail closed: treat missing proof as unchecked non-school for readiness stats.
    return False


def readiness_stats_for_arm(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Correct readiness reporting: only school days are checked."""
    all_rows = list(rows)
    checked = [r for r in all_rows if school_occupied_from_row(r)]
    unchecked = [r for r in all_rows if not school_occupied_from_row(r)]
    ready_checked = [r for r in checked if bool(r.get("readiness_ok"))]
    n_checked = len(checked)
    n_ready = len(ready_checked)
    rate = (float(n_ready) / float(n_checked)) if n_checked else None
    wording = (
        f"Ready on {n_ready}/{n_checked} checked school days; "
        f"{len(unchecked)} non-school days were not subject to the "
        f"school-start readiness gate."
    )
    return {
        "checked_school_days": n_checked,
        "ready_checked_school_days": n_ready,
        "readiness_rate_checked_school_days": rate,
        "unchecked_non_school_days": len(unchecked),
        "all_validation_rows": len(all_rows),
        "checked_school_day_isos": sorted({str(r.get("day")) for r in checked}),
        "unchecked_day_isos": sorted({str(r.get("day")) for r in unchecked}),
        "wording": wording,
        # Misleading aggregate kept only as diagnostic of the old language:
        "legacy_misleading_readiness_ok_rows": sum(1 for r in all_rows if r.get("readiness_ok")),
    }


def arm_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "days": 0,
            "energy_cost": 0.0,
            "incremental_demand_cost": 0.0,
            "peak_kw_max": 0.0,
            "daily_kwh_sum": 0.0,
        }
    )
    for r in rows:
        arm = str(r.get("arm"))
        b = by[arm]
        b["days"] += 1
        b["energy_cost"] += float(r.get("energy_cost") or 0.0)
        b["incremental_demand_cost"] += float(r.get("incremental_demand_cost") or 0.0)
        b["peak_kw_max"] = max(b["peak_kw_max"], float(r.get("peak_kw") or 0.0))
        b["daily_kwh_sum"] += float(r.get("daily_kwh") or 0.0)
    out: dict[str, Any] = {}
    for arm, b in sorted(by.items()):
        ready = readiness_stats_for_arm([r for r in rows if str(r.get("arm")) == arm])
        out[arm] = {
            **b,
            "total_cost": float(b["energy_cost"]) + float(b["incremental_demand_cost"]),
            "readiness": ready,
        }
    return out


def december_floor_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dec15 = [r for r in rows if str(r.get("day"))[:10] == REPRESENTATIVE_DAY]
    openings = [float(r.get("opening_mtd_kw") or 0.0) for r in dec15]
    all_zero = bool(dec15) and all(abs(x) < 1e-12 for x in openings)
    return {
        "representative_day": REPRESENTATIVE_DAY,
        "n_arms_on_dec15": len(dec15),
        "all_opening_mtd_kw_zero": all_zero,
        "opening_mtd_kw_by_arm": {
            str(r.get("arm")): float(r.get("opening_mtd_kw") or 0.0) for r in dec15
        },
        "corrected_scores_published": False,
        "reason_no_rescore": (
            "Campaign exports lack arm-specific 2025-12-01..14 facility/peak series "
            "required to reconstruct the December MTD floor without re-running EnergyPlus."
        ),
        "disclosure": DEC_FLOOR_DISCLOSURE if all_zero else None,
    }


def extract_campaign_block(*, run_root: Path, experiment_id: str) -> dict[str, Any]:
    run_root = Path(run_root)
    manifest = _load_json(run_root / "campaign_manifest.json")
    eval_doc = _load_json(run_root / "eval.json")
    rows = list(eval_doc.get("rows") or [])
    totals = arm_totals(rows)
    raw_leader = eval_doc.get("winner") or eval_doc.get("validation_selected_policy")
    floor = december_floor_audit(rows)
    results = manifest.get("results") or {}
    transitions = {}
    for k, v in results.items():
        if isinstance(v, dict):
            transitions[k] = {
                "timesteps": v.get("timesteps") or v.get("valid_transitions") or manifest.get("target_transitions"),
                "mean_reward_NOT_used_for_leader": v.get("mean_reward"),
            }
    return {
        "experiment_id": experiment_id,
        "tariff_mode": manifest.get("tariff_mode") or eval_doc.get("tariff_mode"),
        "tariff_banner": manifest.get("tariff_banner"),
        "run_root": str(run_root),
        "idf_sha256": manifest.get("idf_sha256"),
        "epw_sha256": manifest.get("epw_sha256"),
        "action_contract_version": manifest.get("action_contract_version")
        or eval_doc.get("action_contract_version"),
        "obs_schema": manifest.get("obs_schema"),
        "observation_dim": manifest.get("observation_dim") or eval_doc.get("observation_dim"),
        "observation_contract": manifest.get("observation_contract"),
        "train_days": list(manifest.get("train_days") or []),
        "validation_days": list(manifest.get("validation_days") or []),
        "n_train_days": len(manifest.get("train_days") or []),
        "n_validation_days": len(manifest.get("validation_days") or []),
        "target_transitions": manifest.get("target_transitions"),
        "rl_transitions_by_model": transitions,
        "validation_arm_days": len(rows),
        "n_eval_arms": len({str(r.get("arm")) for r in rows}),
        "eval_arms": sorted({str(r.get("arm")) for r in rows}),
        "elapsed_s": manifest.get("elapsed_s"),
        "energyplus_severe": manifest.get("energyplus_severe"),
        "energyplus_fatal": manifest.get("energyplus_fatal"),
        "bacnet_commands": manifest.get("bacnet_commands"),
        "actual_energyplus_process_launches": None,
        "actual_energyplus_process_launches_note": (
            "not recorded in campaign_manifest; do not invent"
        ),
        "raw_eval_winner_field": raw_leader,
        "validation_leader": raw_leader,
        "winner_rule": eval_doc.get("winner_rule"),
        "failures": manifest.get("failures") or [],
        "claim_labels": manifest.get("claim_labels") or eval_doc.get("claim_labels"),
        "SIMULATION_TRAINING_READY": manifest.get("SIMULATION_TRAINING_READY"),
        "OPERATIONAL_DSM_READY": manifest.get("OPERATIONAL_DSM_READY"),
        "arm_totals": totals,
        "december_billing_floor": floor,
        "rows": rows,
    }


def baseline_contract_block() -> dict[str, Any]:
    return {
        "campaign_baseline_id": "observed_bas_incumbent_v2",
        "replay_params": {
            "occupied_heating_f": 68.0,
            "unoccupied_heating_f": 64.0,
            "heating_setpoint_start_step": 28,
            "heating_setpoint_end_step": 68,
            "recovery_lead_minutes": 60,
            "continuous_conditioning": False,
            "cooling_occupied_f_approx": 74.0,
            "cooling_unoccupied_f_approx": 85.0,
        },
        "do_not_claim": [
            "Campaign did not compare against continuous 68F heating / 74F cooling thermostat limits.",
            "Modeled cost deltas are not verified savings versus actual BAS operation.",
            "Do not retroactively relabel the historical campaign baseline.",
        ],
        "possible_field_conflict_note": (
            "Reported actual BAS configuration may instead use continuous thermostat "
            "limits of 68F heating and 74F cooling. That conflict was not resolved "
            "before these campaigns."
        ),
    }


def scorecard_rows(block: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    leader = block.get("validation_leader")
    for arm, tot in (block.get("arm_totals") or {}).items():
        ready = tot.get("readiness") or {}
        out.append(
            {
                "experiment_id": block["experiment_id"],
                "tariff_mode": block.get("tariff_mode"),
                "arm": arm,
                "is_validation_leader": arm == leader,
                "days": tot["days"],
                "energy_cost": round(float(tot["energy_cost"]), 6),
                "incremental_demand_cost": round(float(tot["incremental_demand_cost"]), 6),
                "total_cost": round(float(tot["total_cost"]), 6),
                "peak_kw_max": round(float(tot["peak_kw_max"]), 6),
                "daily_kwh_sum": round(float(tot["daily_kwh_sum"]), 6),
                "checked_school_days": ready.get("checked_school_days"),
                "ready_checked_school_days": ready.get("ready_checked_school_days"),
                "readiness_rate_checked_school_days": ready.get(
                    "readiness_rate_checked_school_days"
                ),
                "unchecked_non_school_days": ready.get("unchecked_non_school_days"),
                "all_validation_rows": ready.get("all_validation_rows"),
                "readiness_wording": ready.get("wording"),
            }
        )
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def primary_secondary_summary(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    p_inc = primary["arm_totals"]["incumbent"]
    p_lead_arm = primary["validation_leader"]
    p_lead = primary["arm_totals"][p_lead_arm]
    s_inc = secondary["arm_totals"]["incumbent"]
    s_lead_arm = secondary["validation_leader"]
    s_lead = secondary["arm_totals"][s_lead_arm]
    return {
        "primary": {
            "experiment_id": "FLAT_PLUS_DEMAND",
            "validation_leader": p_lead_arm,
            "incumbent_total_cost": p_inc["total_cost"],
            "leader_total_cost": p_lead["total_cost"],
            "delta_vs_incumbent": p_lead["total_cost"] - p_inc["total_cost"],
            "incumbent_peak_kw": p_inc["peak_kw_max"],
            "leader_peak_kw": p_lead["peak_kw_max"],
            "leader_reduced_peak": False,
            "leader_reduced_total_cost": False,
            "readiness_wording": p_lead["readiness"]["wording"],
            "incumbent_readiness_wording": p_inc["readiness"]["wording"],
        },
        "secondary": {
            "experiment_id": "ILLUSTRATIVE_TOU_PLUS_DEMAND",
            "validation_leader": s_lead_arm,
            "incumbent_total_cost": s_inc["total_cost"],
            "leader_total_cost": s_lead["total_cost"],
            "illustrative_delta_vs_incumbent": s_lead["total_cost"] - s_inc["total_cost"],
            "incumbent_peak_kw": s_inc["peak_kw_max"],
            "leader_peak_kw": s_lead["peak_kw_max"],
            "leader_energy_cost": s_lead["energy_cost"],
            "incumbent_energy_cost": s_inc["energy_cost"],
            "leader_demand_cost": s_lead["incremental_demand_cost"],
            "incumbent_demand_cost": s_inc["incremental_demand_cost"],
            "savings_from_illustrative_tou_energy": s_lead["energy_cost"] < s_inc["energy_cost"],
            "demand_cost_increased": s_lead["incremental_demand_cost"] > s_inc["incremental_demand_cost"],
            "peak_increased": s_lead["peak_kw_max"] > s_inc["peak_kw_max"],
            "readiness_wording": s_lead["readiness"]["wording"],
            "tou_dollars_illustrative_not_verified": True,
        },
        "never_compare_absolute_dollars_across_tariffs": True,
    }


def render_results_markdown(
    *,
    primary: dict[str, Any],
    secondary: dict[str, Any],
    summary: dict[str, Any],
    baseline: dict[str, Any],
) -> str:
    p = summary["primary"]
    s = summary["secondary"]
    labels = "\n".join(f"- `{x}`" for x in HONESTY_LABELS)
    lines = [
        "# Vibe22 RL PoC results (simulation-only)",
        "",
        "## Honesty",
        "",
        labels,
        "",
        "## Baseline contract (historical — not retconned)",
        "",
        f"Both campaigns used **`{baseline['campaign_baseline_id']}`**:",
        "",
        "- Scheduled heating approximately **68°F occupied / 64°F unoccupied**",
        "- Scheduled DualSP transitions (not continuous conditioning)",
        "- Cooling approximately **74°F occupied / 85°F unoccupied**",
        "",
        baseline["possible_field_conflict_note"],
        "",
        "Do **not** claim the campaign compared against continuous 68°F/74°F.",
        "Do **not** present modeled deltas as verified savings versus actual BAS operation.",
        "",
        "## December billing floor disclosure",
        "",
        f"> {DEC_FLOOR_DISCLOSURE}",
        "",
        "Original validation scores are retained; no offline re-score was possible without "
        "arm-specific Dec 1–14 facility series.",
        "",
        "## Experiment scale (do not conflate)",
        "",
        "| Counter | PRIMARY | SECONDARY |",
        "|---|---:|---:|",
        f"| RL transitions per model (PPO/DQN seeds) | {primary.get('target_transitions')} | {secondary.get('target_transitions')} |",
        f"| Validation arm-days (rows) | {primary.get('validation_arm_days')} | {secondary.get('validation_arm_days')} |",
        f"| Train days | {primary.get('n_train_days')} | {secondary.get('n_train_days')} |",
        f"| Validation calendar days | {primary.get('n_validation_days')} | {secondary.get('n_validation_days')} |",
        f"| Actual EnergyPlus process launches | not recorded | not recorded |",
        f"| Elapsed s | {primary.get('elapsed_s')} | {secondary.get('elapsed_s')} |",
        f"| Severe / fatal | {primary.get('energyplus_severe')} / {primary.get('energyplus_fatal')} | {secondary.get('energyplus_severe')} / {secondary.get('energyplus_fatal')} |",
        f"| BACnet commands | {primary.get('bacnet_commands')} | {secondary.get('bacnet_commands')} |",
        "",
        "## PRIMARY — FLAT_PLUS_DEMAND",
        "",
        f"- Validation leader: **`{p['validation_leader']}`** (readiness-constrained; not training mean reward)",
        f"- Incumbent total ≈ **${p['incumbent_total_cost']:.2f}**",
        f"- Leader total ≈ **${p['leader_total_cost']:.2f}**",
        f"- Delta versus incumbent ≈ **${p['delta_vs_incumbent']:+.2f}**",
        f"- Incumbent peak ≈ **{p['incumbent_peak_kw']:.2f} kW**; leader peak ≈ **{p['leader_peak_kw']:.2f} kW**",
        "- Leader **did not** reduce peak or total modeled cost versus the incumbent.",
        f"- Readiness: {p['readiness_wording']}",
        f"- Incumbent readiness: {p['incumbent_readiness_wording']}",
        "",
        "## SECONDARY — ILLUSTRATIVE_TOU_PLUS_DEMAND",
        "",
        f"- Validation leader: **`{s['validation_leader']}`**",
        f"- Incumbent total ≈ **${s['incumbent_total_cost']:.2f}**",
        f"- Leader total ≈ **${s['leader_total_cost']:.2f}**",
        f"- Illustrative delta ≈ **${s['illustrative_delta_vs_incumbent']:+.2f}**",
        f"- Incumbent peak ≈ **{s['incumbent_peak_kw']:.2f} kW**; leader peak ≈ **{s['leader_peak_kw']:.2f} kW**",
        "- Illustrative savings came from the **TOU energy** component; demand cost and peak **increased**.",
        "- TOU dollars are **illustrative** and **not** verified utility savings.",
        f"- Readiness: {s['readiness_wording']}",
        "",
        "**Never compare absolute dollar totals between PRIMARY and SECONDARY as if they were the same tariff.**",
        "",
        "## Figures",
        "",
        "- `docs/results/figures/cost_decomposition_by_tariff.(png|svg)`",
        "- `docs/results/figures/peak_and_readiness_tradeoff.(png|svg)`",
        "- `docs/results/figures/representative_daily_control_plan.(png|svg)`",
        "- `docs/results/figures/representative_day_outcomes.(png|svg)` "
        "(aggregate-from-eval; timestep facility series not retained)",
        "",
        "## Exhaustive discrete screen",
        "",
        "Status: **NOT_RUN** (no exhaustive DQN-table LIVE eval runner; would exceed 60-minute honesty bound).",
        "",
    ]
    return "\n".join(lines)


def build_pack(*, site_root: Path, out_dir: Path) -> dict[str, Any]:
    site_root = Path(site_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    primary = extract_campaign_block(
        run_root=site_root / "reports" / "eplus_gym" / "rl" / PRIMARY_RUN,
        experiment_id="FLAT_PLUS_DEMAND",
    )
    secondary = extract_campaign_block(
        run_root=site_root / "reports" / "eplus_gym" / "rl" / SECONDARY_RUN,
        experiment_id="ILLUSTRATIVE_TOU_PLUS_DEMAND",
    )
    # Drop heavy row payloads from published JSON (keep scorecard derived).
    primary_pub = {k: v for k, v in primary.items() if k != "rows"}
    secondary_pub = {k: v for k, v in secondary.items() if k != "rows"}
    baseline = baseline_contract_block()
    summary = primary_secondary_summary(primary, secondary)
    scorecard = scorecard_rows(primary) + scorecard_rows(secondary)
    write_csv(out_dir / "vibe22_rl_poc_arm_scorecard.csv", scorecard)

    provenance = {
        "schema": "vibe22.rl_poc_provenance.v1",
        "honesty_labels": HONESTY_LABELS,
        "baseline_contract": baseline,
        "primary": {
            k: primary_pub[k]
            for k in (
                "experiment_id",
                "tariff_mode",
                "run_root",
                "idf_sha256",
                "epw_sha256",
                "action_contract_version",
                "obs_schema",
                "observation_dim",
                "observation_contract",
                "train_days",
                "validation_days",
                "n_train_days",
                "n_validation_days",
                "target_transitions",
                "rl_transitions_by_model",
                "validation_arm_days",
                "n_eval_arms",
                "eval_arms",
                "elapsed_s",
                "energyplus_severe",
                "energyplus_fatal",
                "bacnet_commands",
                "actual_energyplus_process_launches",
                "actual_energyplus_process_launches_note",
                "validation_leader",
                "raw_eval_winner_field",
                "winner_rule",
                "failures",
                "december_billing_floor",
            )
        },
        "secondary": {
            k: secondary_pub[k]
            for k in (
                "experiment_id",
                "tariff_mode",
                "run_root",
                "idf_sha256",
                "epw_sha256",
                "action_contract_version",
                "obs_schema",
                "observation_dim",
                "observation_contract",
                "train_days",
                "validation_days",
                "n_train_days",
                "n_validation_days",
                "target_transitions",
                "rl_transitions_by_model",
                "validation_arm_days",
                "n_eval_arms",
                "eval_arms",
                "elapsed_s",
                "energyplus_severe",
                "energyplus_fatal",
                "bacnet_commands",
                "actual_energyplus_process_launches",
                "actual_energyplus_process_launches_note",
                "validation_leader",
                "raw_eval_winner_field",
                "winner_rule",
                "failures",
                "december_billing_floor",
            )
        },
    }
    (out_dir / "vibe22_rl_poc_provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )

    results_json = {
        "schema": "vibe22.rl_poc_results.v1",
        "honesty_labels": HONESTY_LABELS,
        "baseline_contract": baseline,
        "december_billing_floor_disclosure": DEC_FLOOR_DISCLOSURE,
        "summary": summary,
        "primary": primary_pub,
        "secondary": secondary_pub,
        "never_compare_absolute_dollars_across_tariffs": True,
    }
    (out_dir / "vibe22_rl_poc_results.json").write_text(
        json.dumps(results_json, indent=2), encoding="utf-8"
    )
    (out_dir / "vibe22_rl_poc_results.md").write_text(
        render_results_markdown(
            primary=primary, secondary=secondary, summary=summary, baseline=baseline
        ),
        encoding="utf-8",
    )
    (out_dir / "vibe22_rl_poc_exhaustive_discrete_screen.json").write_text(
        json.dumps(
            {
                "schema": "vibe22.exhaustive_discrete_action_screen.v1",
                "status": "NOT_RUN",
                "label_if_run": "EXHAUSTIVE_DISCRETE_ACTION_SCREEN",
                "reason": (
                    "No exhaustive DQN discrete-table LIVE evaluation runner exists; "
                    "building one and simulating the full menu on 17 validation days "
                    "would exceed the 60-minute honesty bound. Marked NOT_RUN."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "baseline_evidence_resolution.json").write_text(
        json.dumps(
            {
                "schema": "vibe22.baseline_evidence_resolution.v1",
                "status": "UNRESOLVED_FIELD_CONFLICT_NOTED",
                "campaign_baseline_unchanged": "observed_bas_incumbent_v2",
                "note": baseline["possible_field_conflict_note"],
                "does_not_alter_historical_campaign_artifacts": True,
                "does_not_claim_policies_evaluated_against_new_baseline": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "primary": primary,
        "secondary": secondary,
        "summary": summary,
        "out_dir": str(out_dir),
    }
