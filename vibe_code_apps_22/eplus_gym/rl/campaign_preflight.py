"""Fail-closed campaign preflight. Does not start EnergyPlus."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

from eplus_gym.a04_identity import is_canonical_a04_idf_filename
from eplus_gym.rl.active_model import ActiveModelError, load_active_model, verify_active_model

PUBLIC_LABELS = (
    "SIMULATION_ONLY_RL_RESEARCH",
    "NOT VALIDATED FOR OPERATIONAL DSM",
    "NO BACNET COMMAND AUTHORITY",
)
REQUIRED_CONTRACTS = {
    "control_contract_version": "control_contract_v2",
    "observation_contract_version": "observation_contract_v3",
    "reward_contract_version": "reward_v2",
}
LEGACY_REWARD = frozenset({"legacy_reward_v1", "operator_pay_2x_v1", "operator_pay_3x_v1"})
ALLOWED_ACTION = frozenset({"ppo_action_contract_v2", "dqn_action_contract_v2"})
PERFECT_FORECAST = "PERFECT_EPISODE_FORECAST"


class PreflightError(ValueError):
    """Campaign preflight failed closed."""


def dates_are_contiguous(days: Sequence[str]) -> bool:
    parsed = [date.fromisoformat(str(d)[:10]) for d in days]
    if len(parsed) < 1:
        return False
    return all(parsed[i] - parsed[i - 1] == timedelta(days=1) for i in range(1, len(parsed)))


def _issue(issues: list[str], cond: bool, msg: str) -> None:
    if cond:
        issues.append(msg)


def preflight_campaign(
    bundle: Mapping[str, Any] | None,
    *,
    app_root: Path,
    require_verified_active: bool = True,
    check_energyplus: bool = True,
) -> dict[str, Any]:
    """Validate long-campaign dependencies without starting EnergyPlus."""
    issues: list[str] = []
    app_root = Path(app_root)
    body = dict(bundle or {})
    if require_verified_active:
        try:
            verify_active_model(app_root)
        except ActiveModelError as exc:
            issues.append(f"no active verified model: {exc}")
        manifest = load_active_model(app_root)
        idf_rel = str(manifest.get("idf_path") or "")
        if idf_rel and is_canonical_a04_idf_filename(idf_rel) and not manifest.get(
            "a04_explicitly_verified_active"
        ):
            issues.append("campaign refuses A04 unless it is explicitly the verified active model")
    days = [str(d)[:10] for d in (body.get("days") or body.get("episode_days") or [])]
    _issue(issues, not days, "episode dates missing")
    _issue(issues, bool(days) and not dates_are_contiguous(days), "non-contiguous episode dates")
    forecasts = body.get("hourly_forecasts") or body.get("hourly_oat") or {}
    for day in days:
        series = forecasts.get(day) if isinstance(forecasts, Mapping) else None
        if not series or len(list(series)) != 24:
            issues.append(f"missing hourly forecasts for {day}")
            break
    src = str(body.get("forecast_source") or "")
    _issue(issues, src != PERFECT_FORECAST, "forecast source must be PERFECT_EPISODE_FORECAST")
    baselines = body.get("paired_baselines") or body.get("baseline_payloads") or {}
    for day in days:
        if day not in (baselines or {}):
            issues.append(f"missing paired baseline artifacts for {day}")
            break
    want_idf = str(body.get("idf_sha256") or "")
    want_epw = str(body.get("epw_sha256") or "")
    got_idf = str(body.get("verified_idf_sha256") or body.get("idf_sha256") or "")
    got_epw = str(body.get("verified_epw_sha256") or body.get("epw_sha256") or "")
    _issue(issues, bool(want_idf) and got_idf != want_idf, "baseline/model/EPW hash mismatch")
    _issue(issues, bool(want_epw) and got_epw != want_epw, "baseline/model/EPW hash mismatch")
    tariff = str(body.get("tariff_status") or body.get("tariff") or "")
    _issue(issues, tariff != "ILLUSTRATIVE", "missing tariff label ILLUSTRATIVE")
    reward = str(body.get("reward_contract_version") or body.get("reward_name") or "")
    _issue(issues, reward in LEGACY_REWARD or reward != "reward_v2", "legacy reward/action/observation contract")
    action = str(body.get("action_contract_version") or "")
    obs = str(body.get("observation_contract_version") or "")
    ctrl = str(body.get("control_contract_version") or "")
    _issue(
        issues,
        action not in ALLOWED_ACTION
        or obs != REQUIRED_CONTRACTS["observation_contract_version"]
        or ctrl != REQUIRED_CONTRACTS["control_contract_version"],
        "legacy reward/action/observation contract",
    )
    if check_energyplus:
        try:
            from eplus_gym.energyplus_cli import energyplus_exe

            exe = energyplus_exe()
            if not Path(exe).is_file():
                issues.append("missing EnergyPlus executable")
        except FileNotFoundError:
            issues.append("missing EnergyPlus executable")
    out = body.get("output_root") or body.get("out")
    if out:
        op = Path(str(out))
        collide = body.get("allow_output_collision") is True
        if op.exists() and any(op.iterdir()) and not collide:
            issues.append("writable output collision")
    ckpt = body.get("checkpoint_manifest")
    if body.get("resume"):
        if not isinstance(ckpt, Mapping):
            issues.append("incomplete checkpoint/resume manifest")
        else:
            need = ("rng", "valid_transition_count", "idf_sha256", "epw_sha256", "episode_block")
            missing = [k for k in need if not ckpt.get(k)]
            if missing:
                issues.append("incomplete checkpoint/resume manifest")
    if issues:
        raise PreflightError("; ".join(issues[:12]))
    return {
        "ok": True,
        "public_labels": list(PUBLIC_LABELS),
        "n_days": len(days),
        "contiguous": True,
    }
