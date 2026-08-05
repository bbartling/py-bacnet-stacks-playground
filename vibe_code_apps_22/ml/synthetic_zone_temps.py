"""DEMO synthetic zone air temps for multi-target heating DSM notebooks.

Honesty
-------
Stamp: ``SYNTHETIC_ZONE_TEMPS`` — physics-ish IdealLoads-style recovery, **not**
native EnergyPlus ``eplusout`` zone temps. Replace with a real B2 farm when ready.

Used to prove the multi-output + 24h causal walk contract (facility_kW + 6 Areas)
before the native E+ control-varied farm lands.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from feature_compile_heating_dsm import HP_ON_COLS, OCC_FRAC_COLS, ZONE_TEMP_COLS

# Default DEMO knobs (notebooks re-declare these visibly for readers)
DEFAULT_DEMO_KNOBS: dict[str, Any] = {
    "midnight_zone_f": 62.0,
    "occ_sp_f": 68.0,
    "unocc_sp_f": 60.0,
    "ua_proxy": 0.03,  # fraction toward envelope sink (OAT/unocc blend) per hour
    "hp_gain": 3.2,  # °F toward setpoint per hour when HP on (cold day)
    "solar_gain": 0.004,  # °F per W/m² GHI
    "internal_gain": 0.35,  # °F per unit occ_frac
    "noise_std": 0.15,
    "seed": 21,
}


def _zone_short(temp_col: str) -> str:
    # zone_temp_1F_A_f → 1F_A
    return temp_col.replace("zone_temp_", "").replace("_f", "")


def attach_synthetic_zone_temps(
    farm_df: pd.DataFrame,
    *,
    midnight_zone_f: float = 62.0,
    occ_sp_f: float = 68.0,
    unocc_sp_f: float = 60.0,
    ua_proxy: float = 0.03,
    hp_gain: float = 3.2,
    solar_gain: float = 0.004,
    internal_gain: float = 0.35,
    noise_std: float = 0.15,
    seed: int = 21,
) -> pd.DataFrame:
    """Append 6 zone_temp_*_f columns via a causal hour walk per simulation_id.

    Each Area tracks its own state. HP on pulls toward occupied SP; HP off drifts
    toward unoccupied SP with OAT coupling. Strategy already encoded in hp_on /
    occ_frac / setpoints on the farm rows.
    """
    need = {"hour_ending", "oat_f", "facility_kw", *OCC_FRAC_COLS}
    missing = need - set(farm_df.columns)
    if missing:
        raise ValueError(f"farm frame missing {sorted(missing)}")

    out = farm_df.copy()
    for c in HP_ON_COLS:
        if c not in out.columns:
            short = c.replace("hp_on_", "occ_frac_")
            out[c] = (out[short] > 0.05).astype(float)

    gcol = "simulation_id" if "simulation_id" in out.columns else "day"
    rng = np.random.default_rng(seed)
    # Positional arrays aligned with out after reset
    out = out.reset_index(drop=True)
    temps = {c: np.zeros(len(out), dtype=float) for c in ZONE_TEMP_COLS}

    for _, sub in out.groupby(gcol, sort=False):
        sub = sub.sort_values("hour_ending")
        state = {c: float(midnight_zone_f) for c in ZONE_TEMP_COLS}
        for i, c in enumerate(ZONE_TEMP_COLS):
            state[c] += 0.4 * (i - 2.5)

        for pos in sub.index.tolist():
            row = out.loc[pos]
            oat = float(row["oat_f"])
            ghi = float(row["ghi"]) if "ghi" in out.columns else 0.0
            unocc_sp = float(row["unocc_htg_sp_f"]) if "unocc_htg_sp_f" in out.columns else unocc_sp_f
            occ_sp = float(row["occ_htg_sp_f"]) if "occ_htg_sp_f" in out.columns else occ_sp_f
            if np.isnan(unocc_sp):
                unocc_sp = unocc_sp_f
            if np.isnan(occ_sp):
                occ_sp = occ_sp_f

            for zcol in ZONE_TEMP_COLS:
                short = _zone_short(zcol)
                occ = float(row.get(f"occ_frac_{short}", 0.0) or 0.0)
                hp = float(row.get(f"hp_on_{short}", 0.0) or 0.0)
                t = state[zcol]
                # Envelope sink: blend OAT with unocc SP so winter nights set back, not freeze
                sink = 0.35 * oat + 0.65 * unocc_sp
                t = t + ua_proxy * (sink - t)
                t = t + internal_gain * occ + solar_gain * (0.0 if np.isnan(ghi) else ghi)
                if hp > 0.5:
                    target = occ_sp if occ > 0.05 else max(unocc_sp, occ_sp - 2.0)
                    gain = hp_gain * (0.7 + 0.3 * min(1.0, max(0.0, (65.0 - oat) / 40.0)))
                    t = t + gain * np.tanh((target - t) / 4.0)
                else:
                    t = t + 0.45 * np.tanh((unocc_sp - t) / 5.0)
                t = t + float(rng.normal(0.0, noise_std))
                t = float(np.clip(t, 50.0, 85.0))
                state[zcol] = t
                temps[zcol][pos] = t

    for c in ZONE_TEMP_COLS:
        out[c] = temps[c]

    out["zone_temp_provenance"] = "SYNTHETIC_ZONE_TEMPS"
    out["zone_temp_honesty"] = (
        "DEMO IdealLoads-style zone temps for multi-target walk — not native eplusout."
    )
    # Preserve / annotate overall provenance
    if "provenance" in out.columns:
        out["provenance"] = out["provenance"].astype(str) + "+SYNTHETIC_ZONE_TEMPS"
    else:
        out["provenance"] = "SYNTHETIC_ZONE_TEMPS"
    return out


__all__ = [
    "DEFAULT_DEMO_KNOBS",
    "attach_synthetic_zone_temps",
]
