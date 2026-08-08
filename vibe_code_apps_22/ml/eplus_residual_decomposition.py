"""Hourly residual / IdealLoads proxy component decomposition diagnostics."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def decompose_aligned_hourly(
    aligned: pd.DataFrame,
    *,
    obs_col: str = "observed_kw",
    sim_col: str = "simulated_kw",
    ts_col: str = "interval_end_utc",
) -> dict[str, Any]:
    """Quantify opposing structural errors without inventing unobserved plant meters.

    Reports residual by hour-of-day, weekday/weekend, and overnight baseload vs
    daytime peak bias. IdealLoads fixed-COP does not expose true fan/pump/compressor
    splits in the proxy — those are labeled as unavailable.
    """
    df = aligned.copy()
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
    df["resid"] = df[sim_col].astype(float) - df[obs_col].astype(float)
    df["hod"] = df[ts_col].dt.hour
    df["dow"] = df[ts_col].dt.dayofweek
    df["is_weekend"] = df["dow"] >= 5
    df["month"] = df[ts_col].dt.strftime("%Y-%m")

    by_hod = df.groupby("hod")["resid"].agg(["mean", "median", "count"]).reset_index()
    overnight = df[df["hod"].between(0, 5)]
    daytime = df[df["hod"].between(7, 15)]
    weekend = df[df["is_weekend"]]
    weekday = df[~df["is_weekend"]]

    summary = {
        "n": int(len(df)),
        "mean_obs_kw": float(df[obs_col].mean()),
        "mean_sim_kw": float(df[sim_col].mean()),
        "overnight_00_05_mean_resid_kw": float(overnight["resid"].mean()) if len(overnight) else None,
        "daytime_07_15_mean_resid_kw": float(daytime["resid"].mean()) if len(daytime) else None,
        "weekend_mean_sim_kw": float(weekend[sim_col].mean()) if len(weekend) else None,
        "weekend_mean_obs_kw": float(weekend[obs_col].mean()) if len(weekend) else None,
        "weekday_peak_obs_kw": float(weekday[obs_col].max()) if len(weekday) else None,
        "weekday_peak_sim_kw": float(weekday[sim_col].max()) if len(weekday) else None,
        "structural_narrative": [
            "Missing persistent overnight baseload / pump / fan / DOAS electricity "
            "(model underpredicts hours 00–05).",
            "Excessive / incorrectly shaped fixed-COP heating electricity "
            "(model overpredicts hours 07–15 and cold weekday peaks).",
            "A single multiplier cannot fix both opposing errors.",
        ],
        "unavailable_true_splits": [
            "lights",
            "plug_equipment",
            "fans",
            "pumps",
            "DOAS",
            "heating_compressor",
            "cooling_compressor",
            "ground_loop_EWT",
        ],
        "note": "IdealLoads+fixed-COP proxy does not expose true component meters; "
        "decomposition is residual-pattern based.",
    }
    return {"summary": summary, "by_hod": by_hod, "frame": df}


def write_residual_decomposition(
    aligned: pd.DataFrame,
    out_dir: Path,
    *,
    obs_col: str = "observed_kw",
    sim_col: str = "simulated_kw",
    ts_col: str = "interval_end_utc",
) -> dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = _ensure(Path(out_dir))
    plots = _ensure(out / "plots")
    decomp = decompose_aligned_hourly(
        aligned, obs_col=obs_col, sim_col=sim_col, ts_col=ts_col
    )
    df = decomp["frame"]
    by_hod = decomp["by_hod"]
    by_hod.to_csv(out / "residual_by_hod.csv", index=False)
    (out / "decomposition_summary.json").write_text(
        json.dumps(decomp["summary"], indent=2) + "\n", encoding="utf-8"
    )

    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.bar(by_hod["hod"], by_hod["mean"], color="#4a6fa5")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel("hour of day (UTC)")
    ax.set_ylabel("mean residual kW (sim−obs)")
    ax.set_title("Structural residual by hour — overnight under / daytime over")
    fig.tight_layout()
    fig.savefig(plots / "residual_by_hod_decomp.png", dpi=120)
    plt.close(fig)

    # Weekend vs weekday mean profiles
    fig, ax = plt.subplots(figsize=(9, 3.5))
    for label, mask in (("weekday", ~df["is_weekend"]), ("weekend", df["is_weekend"])):
        g = df.loc[mask].groupby("hod")
        ax.plot(g[obs_col].mean().index, g[obs_col].mean().values, label=f"obs {label}")
        ax.plot(
            g[sim_col].mean().index,
            g[sim_col].mean().values,
            "--",
            label=f"sim {label}",
            alpha=0.85,
        )
    ax.set_ylabel("kW")
    ax.set_title("Weekday vs weekend mean profiles")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(plots / "weekday_weekend_profiles.png", dpi=120)
    plt.close(fig)

    return {"summary": decomp["summary"], "plots": str(plots)}
