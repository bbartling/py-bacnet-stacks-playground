"""Independent EnergyPlus-versus-ESCO proxy comparisons."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

VERDICTS = {
    "IN_LINE",
    "REASONABLE_METHOD_DIFFERENCE",
    "INVESTIGATE_INPUTS",
    "ENERGYPLUS_BEHAVIORALLY_IMPLAUSIBLE",
    "PROXY_OUTSIDE_APPLICABILITY",
    "INSUFFICIENT_EVIDENCE",
}


def compare_proxy_results(
    scenario_results: Sequence[Mapping[str, Any]],
    proxies: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Compare methods without treating either method as ground truth."""
    proxies = proxies or {}
    rows: list[dict[str, Any]] = []
    for result in scenario_results:
        scenario_id = str(result.get("scenario_id"))
        proxy = proxies.get(scenario_id, {})
        modeled = result.get("savings_kwh")
        proxy_value = proxy.get("savings_kwh")
        applicable = proxy.get("applicable", True)
        if not applicable:
            verdict = "PROXY_OUTSIDE_APPLICABILITY"
        elif modeled is None or proxy_value is None:
            verdict = "INSUFFICIENT_EVIDENCE"
        elif float(modeled) < 0 and not result.get("unmet_hours"):
            verdict = "ENERGYPLUS_BEHAVIORALLY_IMPLAUSIBLE"
        else:
            denominator = max(abs(float(proxy_value)), 1.0)
            difference = abs(float(modeled) - float(proxy_value)) / denominator
            verdict = (
                "IN_LINE"
                if difference <= 0.2
                else "REASONABLE_METHOD_DIFFERENCE"
                if difference <= 0.5
                else "INVESTIGATE_INPUTS"
            )
        rows.append(
            {
                "scenario_id": scenario_id,
                "energyplus_savings_kwh": modeled,
                "proxy_savings_kwh": proxy_value,
                "verdict": verdict,
                "note": proxy.get("note")
                or "Independent methods are compared; agreement is not forced.",
            }
        )
    return rows
