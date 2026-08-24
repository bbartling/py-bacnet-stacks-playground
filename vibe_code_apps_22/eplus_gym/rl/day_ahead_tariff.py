"""Day-ahead tariff forecast adapter (local fixtures only; no commercial API)."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np

SCHEMA = "vibe22.day_ahead_tariff_forecast.v1"
ILLUSTRATIVE_BANNER = "ILLUSTRATIVE TARIFF — NOT VERIFIED UTILITY PRICING"
DEFAULT_ENERGY = 0.11
DEFAULT_DEMAND = 12.0
MAX_FRESHNESS_S = 7 * 24 * 3600


class TariffContractError(ValueError):
    pass


def expand_hourly_to_96(hourly: Sequence[float]) -> list[float]:
    if len(hourly) != 24:
        raise TariffContractError(f"hourly energy_prices must have length 24, got {len(hourly)}")
    return [float(h) for h in hourly for _ in range(4)]


def provenance_hash(body: dict[str, Any]) -> str:
    payload = {k: v for k, v in body.items() if k != "provenance"}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_day_ahead_tariff(doc: dict[str, Any], *, now_iso: str | None = None) -> dict[str, Any]:
    if doc.get("schema") != SCHEMA:
        raise TariffContractError(f"schema must be {SCHEMA}")
    if doc.get("energy_price_unit") != "USD_per_kWh":
        raise TariffContractError("energy_price_unit must be USD_per_kWh")
    if doc.get("currency") != "USD":
        raise TariffContractError("currency must be USD")
    interval = int(doc.get("interval_minutes") or 0)
    prices = list(doc.get("energy_prices") or [])
    if interval == 60:
        if len(prices) != 24:
            raise TariffContractError("interval_minutes=60 requires 24 energy_prices")
        qh = expand_hourly_to_96(prices)
    elif interval == 15:
        if len(prices) != 96:
            raise TariffContractError("interval_minutes=15 requires 96 energy_prices")
        qh = [float(x) for x in prices]
    else:
        raise TariffContractError("interval_minutes must be 15 or 60")
    for i, x in enumerate(qh):
        if not math.isfinite(x):
            raise TariffContractError(f"non-finite energy price at interval {i}")
        if x < 0:
            raise TariffContractError(f"negative energy price at interval {i} (not supported)")
    for key in (
        "demand_rate_usd_per_kw",
        "month_to_date_peak_kw",
        "ratchet_floor_kw",
        "contract_demand_floor_kw",
    ):
        v = float(doc[key])
        if not math.isfinite(v) or v < 0:
            raise TariffContractError(f"{key} must be finite and >= 0")
    if doc.get("missing_interval_policy") not in {"reject", "fail_closed"}:
        raise TariffContractError("missing_interval_policy must be reject or fail_closed")
    if int(doc.get("freshness_seconds") or 0) > MAX_FRESHNESS_S:
        raise TariffContractError("stale tariff: freshness_seconds exceeds max")
    if not doc.get("timezone"):
        raise TariffContractError("timezone required")
    if not doc.get("effective_start"):
        raise TariffContractError("effective_start required")
    prov = dict(doc.get("provenance") or {})
    expected = provenance_hash(doc)
    if prov.get("hash") and str(prov["hash"]) != expected:
        raise TariffContractError("provenance.hash mismatch")
    out = dict(doc)
    out["_quarter_hour_prices"] = qh
    out["_provenance_hash"] = expected
    if not bool(out.get("verified_tariff")):
        out["banner"] = out.get("banner") or ILLUSTRATIVE_BANNER
    _ = now_iso
    return out


def load_day_ahead_tariff(path: Path) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_day_ahead_tariff(doc)


def build_fixture(
    *,
    source: str,
    energy_prices_hourly: Sequence[float],
    demand_rate: float = DEFAULT_DEMAND,
    mtd: float = 0.0,
    verified: bool = False,
    effective_start: str = "2025-12-15T00:00:00-06:00",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "version": "1.0.0",
        "source": source,
        "generated_at": "2026-08-21T00:00:00Z",
        "timezone": "America/Chicago",
        "effective_start": effective_start,
        "interval_minutes": 60,
        "currency": "USD",
        "energy_price_unit": "USD_per_kWh",
        "energy_prices": [float(x) for x in energy_prices_hourly],
        "demand_rate_usd_per_kw": float(demand_rate),
        "month_to_date_peak_kw": float(mtd),
        "ratchet_floor_kw": 0.0,
        "contract_demand_floor_kw": 0.0,
        "verified_tariff": bool(verified),
        "freshness_seconds": 3600,
        "missing_interval_policy": "fail_closed",
        "banner": ILLUSTRATIVE_BANNER if not verified else None,
    }
    body["provenance"] = {"hash": provenance_hash(body), "notes": "local fixture; no commercial API"}
    return body


def flat_plus_demand_fixture() -> dict[str, Any]:
    return build_fixture(
        source="fixture:flat_plus_demand",
        energy_prices_hourly=[DEFAULT_ENERGY] * 24,
    )


def illustrative_evening_tou_fixture() -> dict[str, Any]:
    rates = [DEFAULT_ENERGY * 0.75] * 24
    for h in range(16, 21):
        rates[h] = DEFAULT_ENERGY * 1.5
    return build_fixture(
        source="fixture:illustrative_evening_tou",
        energy_prices_hourly=rates,
    )


def illustrative_dynamic_hourly_fixture() -> dict[str, Any]:
    # Visibly changing 24-hour vector (API-style illustrative).
    rates = [
        0.06,
        0.06,
        0.05,
        0.05,
        0.05,
        0.07,
        0.09,
        0.11,
        0.12,
        0.10,
        0.09,
        0.08,
        0.08,
        0.09,
        0.11,
        0.14,
        0.18,
        0.22,
        0.20,
        0.15,
        0.12,
        0.10,
        0.08,
        0.07,
    ]
    return build_fixture(
        source="fixture:illustrative_dynamic_hourly",
        energy_prices_hourly=rates,
    )


def write_default_fixtures(dir_path: Path) -> dict[str, Path]:
    dir_path = Path(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)
    mapping = {
        "flat_plus_demand.json": flat_plus_demand_fixture(),
        "illustrative_evening_tou.json": illustrative_evening_tou_fixture(),
        "illustrative_dynamic_hourly.json": illustrative_dynamic_hourly_fixture(),
    }
    out: dict[str, Path] = {}
    for name, body in mapping.items():
        p = dir_path / name
        p.write_text(json.dumps(body, indent=2), encoding="utf-8")
        out[name] = p
    return out


def rate_vector_from_mode_or_fixture(mode: str, *, fixtures_dir: Path | None = None) -> tuple[np.ndarray, float, str]:
    """Return (96 rate_kwh, demand_rate, label)."""
    root = Path(fixtures_dir) if fixtures_dir else Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "tariffs"
    if mode in {"FLAT_PLUS_DEMAND", "flat_plus_demand"}:
        doc = load_day_ahead_tariff(root / "flat_plus_demand.json")
        return np.asarray(doc["_quarter_hour_prices"], dtype=float), float(doc["demand_rate_usd_per_kw"]), "FLAT_PLUS_DEMAND"
    if mode in {"ILLUSTRATIVE_TOU_PLUS_DEMAND", "illustrative_evening_tou"}:
        doc = load_day_ahead_tariff(root / "illustrative_evening_tou.json")
        return (
            np.asarray(doc["_quarter_hour_prices"], dtype=float),
            float(doc["demand_rate_usd_per_kw"]),
            "ILLUSTRATIVE_TOU_PLUS_DEMAND",
        )
    if mode in {"ILLUSTRATIVE_DYNAMIC_HOURLY", "illustrative_dynamic_hourly"}:
        doc = load_day_ahead_tariff(root / "illustrative_dynamic_hourly.json")
        return (
            np.asarray(doc["_quarter_hour_prices"], dtype=float),
            float(doc["demand_rate_usd_per_kw"]),
            "ILLUSTRATIVE_DYNAMIC_HOURLY",
        )
    raise TariffContractError(f"unknown tariff mode {mode!r}")
