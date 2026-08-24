"""Write the 10-slide evidence outline for the Vibe22 RL PoC pack."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from eplus_gym.rl.poc_results_publish import HONESTY_LABELS


def write_slide_outline(
    path: Path,
    *,
    summary: dict[str, Any],
    primary: dict[str, Any],
    secondary: dict[str, Any],
) -> None:
    p = summary["primary"]
    s = summary["secondary"]
    honesty = "; ".join(HONESTY_LABELS)
    slides = [
        {
            "n": 1,
            "title": "School and winter demand problem",
            "claim": "Winter electric demand at Lakeside is a billing and operations problem, not a training-curve problem.",
            "figure": "docs/results/figures/peak_and_readiness_tradeoff.png",
            "artifacts": [
                "docs/results/vibe22_rl_poc_provenance.json",
                "$SITE_ROOT/utilities/electricity_utility_demand.csv",
            ],
            "notes": "Open with utility winter peaks and school-day comfort constraints; do not lead with RL rewards.",
            "caveat": "Utility bills are site evidence; RL dollars are modeled under illustrative tariffs.",
            "provenance": honesty,
        },
        {
            "n": 2,
            "title": "BAS, utility and weather evidence",
            "claim": "Campaigns replayed observed_bas_incumbent_v2 (68/64 scheduled), not a continuous 68/74 thermostat claim.",
            "figure": "docs/results/figures/representative_daily_control_plan.png",
            "artifacts": [
                "contracts/observed_bas_incumbent_v2.json",
                "docs/results/baseline_evidence_resolution.json",
            ],
            "notes": "State the possible field conflict (continuous 68/74) without retconning the campaign baseline.",
            "caveat": "Modeled savings are not verified versus actual BAS operation.",
            "provenance": "baseline_contract unchanged for historical campaigns",
        },
        {
            "n": 3,
            "title": "A04 calibration and physics limitations",
            "claim": "A04 is the research IDF; it is not a transient-validated physics champion.",
            "figure": None,
            "artifacts": [
                "docs/results/vibe22_rl_poc_provenance.json",
                f"idf_sha256={primary.get('idf_sha256')}",
            ],
            "notes": "Keep Terminal B / research limits visible on every A04 claim.",
            "caveat": "A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION",
            "provenance": honesty,
        },
        {
            "n": 4,
            "title": "Six-zone EnergyPlus Gym",
            "claim": "Actions actuate six DualSP heating schedules; school occupancy calendar is immutable.",
            "figure": "docs/results/figures/representative_daily_control_plan.png",
            "artifacts": [
                "eplus_gym/control_v2.py",
                "contracts/school_calendar_v2.json",
            ],
            "notes": "Show school window vs heating recovery; extension does not invent holiday occupancy.",
            "caveat": "Cooling remains approximately fixed (~74/85); not optimized.",
            "provenance": "research_action_contract_v3",
        },
        {
            "n": 5,
            "title": "PPO/DQN action spaces",
            "claim": "PPO Box10 + DQN discrete table under research_action_contract_v3; continuous 68/70 reachable.",
            "figure": None,
            "artifacts": [
                "eplus_gym/rl/research_spaces.py",
                f"action_contract={primary.get('action_contract_version')}",
                f"obs_schema={primary.get('obs_schema')} dim={primary.get('observation_dim')}",
            ],
            "notes": "Do not describe the discrete table as an exhaustive LIVE screen (NOT_RUN).",
            "caveat": "docs/results/vibe22_rl_poc_exhaustive_discrete_screen.json status NOT_RUN",
            "provenance": honesty,
        },
        {
            "n": 6,
            "title": "Reward and paired-baseline calculation",
            "claim": "Validation leaders use deterministic costs + readiness, never training mean reward.",
            "figure": "docs/results/figures/cost_decomposition_by_tariff.png",
            "artifacts": [
                "eplus_gym/rl/reward_v2.py",
                primary.get("winner_rule"),
            ],
            "notes": "Explain energy vs incremental demand; readiness checked only on school days.",
            "caveat": "December billing floor opened at 0 kW on 2025-12-15.",
            "provenance": "docs/results/vibe22_rl_poc_results.md December disclosure",
        },
        {
            "n": 7,
            "title": "Experiment scale and provenance",
            "claim": "Distinguish RL transitions (8192×4), validation arm-days (187), and unrecorded E+ process launches.",
            "figure": None,
            "artifacts": [
                "docs/results/vibe22_rl_poc_provenance.json",
                primary.get("run_root"),
                secondary.get("run_root"),
            ],
            "notes": "Say 'not recorded' for process count; do not invent.",
            "caveat": "actual_energyplus_process_launches is null in manifests.",
            "provenance": honesty,
        },
        {
            "n": 8,
            "title": "Flat-tariff result",
            "claim": (
                f"PRIMARY validation leader `{p['validation_leader']}` ≈ ${p['leader_total_cost']:.2f} "
                f"vs incumbent ≈ ${p['incumbent_total_cost']:.2f} (Δ ${p['delta_vs_incumbent']:+.2f}); "
                f"peak {p['leader_peak_kw']:.1f} vs {p['incumbent_peak_kw']:.1f} kW."
            ),
            "figure": "docs/results/figures/cost_decomposition_by_tariff.png",
            "artifacts": [
                "docs/results/vibe22_rl_poc_arm_scorecard.csv",
                "docs/results/vibe22_rl_poc_results.json",
            ],
            "notes": (
                f"Leader did not reduce peak or cost. Readiness: {p['readiness_wording']} "
                f"Incumbent: {p['incumbent_readiness_wording']}"
            ),
            "caveat": "Never say 17/17 school readiness; use checked-school wording.",
            "provenance": "FLAT_PLUS_DEMAND only",
        },
        {
            "n": 9,
            "title": "Illustrative-TOU result",
            "claim": (
                f"SECONDARY validation leader `{s['validation_leader']}` illustrative Δ "
                f"${s['illustrative_delta_vs_incumbent']:+.2f}; energy down, demand/peak up."
            ),
            "figure": "docs/results/figures/peak_and_readiness_tradeoff.png",
            "artifacts": [
                "docs/results/vibe22_rl_poc_arm_scorecard.csv",
                secondary.get("run_root"),
            ],
            "notes": "Do not compare absolute $ to PRIMARY. TOU is illustrative.",
            "caveat": "TOU TARIFF IS ILLUSTRATIVE — NOT VERIFIED UTILITY PRICING",
            "provenance": "ILLUSTRATIVE_TOU_PLUS_DEMAND only; never mix rankings",
        },
        {
            "n": 10,
            "title": "Honest conclusion and deployment boundary",
            "claim": "Simulation-only research PoC; not operational DSM; no BACnet authority; no pristine locked test.",
            "figure": "docs/results/figures/representative_day_outcomes.png",
            "artifacts": [
                "docs/results/vibe22_rl_poc_results.md",
                "docs/results/vibe22_rl_poc_exhaustive_discrete_screen.json",
            ],
            "notes": "End on boundaries: Terminal B A04 limits, Dec floor disclosure, baseline contract.",
            "caveat": honesty,
            "provenance": honesty,
        },
    ]
    lines = [
        "# Vibe22 RL PoC — 10-slide evidence outline",
        "",
        f"Honesty: {honesty}",
        "",
    ]
    for sl in slides:
        lines.extend(
            [
                f"## Slide {sl['n']}: {sl['title']}",
                "",
                f"- **Primary claim:** {sl['claim']}",
                f"- **Figure path:** `{sl['figure']}`" if sl["figure"] else "- **Figure path:** _(none — artifacts only)_",
                "- **Supporting artifacts:**",
            ]
        )
        for a in sl["artifacts"]:
            lines.append(f"  - `{a}`")
        lines.extend(
            [
                f"- **Speaker notes:** {sl['notes']}",
                f"- **Limitation / caveat:** {sl['caveat']}",
                f"- **Source / provenance:** {sl['provenance']}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
