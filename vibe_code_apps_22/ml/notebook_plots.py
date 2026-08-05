"""Plot helpers for Lakeside heating DSM notebooks (Kaggle / competition style)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def family_cv_mae_bars(
    leaderboard: list[dict[str, Any]],
    persistence_peak: float,
    ax=None,
):
    ax = ax or plt.gca()
    names = [e["family"] for e in leaderboard]
    maes = [e["oof_metrics"]["mae_peak_05_09"] for e in leaderboard]
    colors = ["#2a9d8f" if m < persistence_peak else "#e76f51" for m in maes]
    ax.barh(names, maes, color=colors)
    ax.axvline(persistence_peak, color="#264653", ls="--", label=f"persistence {persistence_peak:.2f}")
    ax.set_xlabel("OOF morning-peak MAE (HE 05–09) [kW]")
    ax.set_title("Family bake-off — morning peak MAE (lower is better)")
    ax.legend(loc="best")
    return ax


def family_mae_rmse_grouped(
    leaderboard: list[dict[str, Any]],
    persistence: dict[str, float] | None = None,
    ax=None,
):
    ax = ax or plt.gca()
    names = [e["family"] for e in leaderboard]
    mae = [e["oof_metrics"]["mae"] for e in leaderboard]
    rmse = [e["oof_metrics"]["rmse"] for e in leaderboard]
    x = np.arange(len(names))
    w = 0.38
    ax.bar(x - w / 2, mae, w, label="OOF MAE", color="#4C78A8")
    ax.bar(x + w / 2, rmse, w, label="OOF RMSE", color="#F58518")
    if persistence:
        if "mae" in persistence:
            ax.axhline(persistence["mae"], color="#E45756", ls="--", lw=1.4, label=f"persist MAE={persistence['mae']:.1f}")
        if "rmse" in persistence:
            ax.axhline(persistence["rmse"], color="#B279A2", ls=":", lw=1.4, label=f"persist RMSE={persistence['rmse']:.1f}")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_ylabel("kW")
    ax.set_title("Model family accuracy — MAE vs RMSE (GroupKFold OOF)")
    ax.legend(frameon=False, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def leaderboard_table(
    leaderboard: list[dict[str, Any]],
    persistence: dict[str, float] | None = None,
) -> pd.DataFrame:
    rows = []
    for e in leaderboard:
        m = e["oof_metrics"]
        rows.append(
            {
                "family": e["family"],
                "mae": m["mae"],
                "rmse": m["rmse"],
                "mae_peak_05_09": m["mae_peak_05_09"],
                "rmse_peak_05_09": m["rmse_peak_05_09"],
            }
        )
    out = pd.DataFrame(rows).sort_values("mae_peak_05_09").reset_index(drop=True)
    if persistence:
        out.attrs["persistence"] = persistence
    return out


def metrics_scorecard(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    peak: np.ndarray | None = None,
    *,
    label: str = "champion",
) -> pd.DataFrame:
    """Competition-style MAE / RMSE / R² overall + morning peak."""
    rows = [
        {
            "split": "all_hours",
            "model": label,
            "mae": float(mean_absolute_error(y_true, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "r2": float(r2_score(y_true, y_pred)),
            "n": int(len(y_true)),
        }
    ]
    if peak is not None and np.any(peak):
        rows.append(
            {
                "split": "peak_HE_05_09",
                "model": label,
                "mae": float(mean_absolute_error(y_true[peak], y_pred[peak])),
                "rmse": float(np.sqrt(mean_squared_error(y_true[peak], y_pred[peak]))),
                "r2": float(r2_score(y_true[peak], y_pred[peak])),
                "n": int(peak.sum()),
            }
        )
    return pd.DataFrame(rows)


def oat_vs_kw_scatter(df: pd.DataFrame, ax=None, sample: int = 8000):
    ax = ax or plt.gca()
    sub = df
    if len(sub) > sample:
        sub = sub.sample(sample, random_state=21)
    ax.scatter(sub["oat_f"], sub["facility_kw"], s=6, alpha=0.25, c="#4C78A8")
    ax.set_xlabel("OAT [°F]")
    ax.set_ylabel("facility_kw")
    ax.set_title("OAT vs facility demand (train farm)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def strategy_morning_peak_bars(df: pd.DataFrame, ax=None):
    ax = ax or plt.gca()
    morning = df[(df["hour_ending"] >= 5) & (df["hour_ending"] <= 9)]
    g = morning.groupby("strategy_id")["facility_kw"].mean().sort_values(ascending=False)
    ax.barh(g.index.astype(str), g.values, color="#2a9d8f")
    ax.set_xlabel("Mean facility_kw in HE 05–09")
    ax.set_title("Morning-window mean kW by strategy")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def example_day_profiles(df: pd.DataFrame, day: str, ax=None):
    ax = ax or plt.gca()
    sub = df[df["day"] == day]
    for sid, g in sub.groupby("strategy_id"):
        g = g.sort_values("hour_ending")
        ax.plot(g["hour_ending"], g["facility_kw"], label=sid, lw=1.8)
    ax.set_xlabel("Hour (local)")
    ax.set_ylabel("facility_kw")
    ax.set_title(f"Strategy shapes — {day}")
    ax.legend(fontsize=7, frameon=False, ncol=2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def residual_hist(y_true: np.ndarray, y_pred: np.ndarray, ax=None):
    ax = ax or plt.gca()
    resid = y_true - y_pred
    ax.hist(resid, bins=40, color="#a8dadc", edgecolor="#1d3557", alpha=0.9)
    ax.axvline(0, color="#e63946", ls="--")
    ax.set_xlabel("Residual (actual − pred) [kW]")
    ax.set_title("OOF residual distribution")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def pred_vs_actual(y_true: np.ndarray, y_pred: np.ndarray, ax=None, title: str = "OOF pred vs actual"):
    ax = ax or plt.gca()
    ax.scatter(y_true, y_pred, s=8, alpha=0.35, c="#457b9d")
    lo = float(min(y_true.min(), y_pred.min()))
    hi = float(max(y_true.max(), y_pred.max()))
    ax.plot([lo, hi], [lo, hi], "k--", lw=1)
    ax.set_xlabel("Actual facility_kw")
    ax.set_ylabel("Predicted facility_kw")
    ax.set_title(title)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    ax.text(
        0.02,
        0.98,
        f"MAE={mae:.2f}\nRMSE={rmse:.2f}\nR²={r2:.3f}",
        transform=ax.transAxes,
        va="top",
        fontsize=9,
        family="monospace",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def feature_importance_bar(model: Any, feature_names: list[str], top_n: int = 15, ax=None):
    ax = ax or plt.gca()
    if not hasattr(model, "feature_importances_"):
        ax.text(0.5, 0.5, "no feature_importances_ on this family", ha="center")
        return ax
    imp = np.asarray(model.feature_importances_, dtype=float)
    order = np.argsort(imp)[::-1][:top_n]
    labels = [feature_names[i] for i in order][::-1]
    vals = imp[order][::-1]
    colors = ["#e76f51" if "lag" in lab else "#2a9d8f" for lab in labels]
    ax.barh(labels, vals, color=colors)
    ax.set_xlabel("Importance")
    ax.set_title(f"Top {top_n} feature importances (orange = lag)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def explainer_vs_target_grid(
    df: pd.DataFrame,
    feature_cols: list[str] | None = None,
    *,
    sample: int = 4000,
    axs=None,
):
    """Scatter key explainers vs facility_kw (incl. lags)."""
    cols = feature_cols or [
        "oat_f",
        "hdd65",
        "facility_kw_lag1",
        "sum_hp_on",
        "hours_to_occupy",
        "sum_occ_frac",
    ]
    feat = df
    if "facility_kw_lag1" not in feat.columns:
        from feature_compile_heating_dsm import compile_features

        feat = compile_features(df)
    if len(feat) > sample:
        feat = feat.sample(sample, random_state=21)
    if axs is None:
        fig, axs = plt.subplots(2, 3, figsize=(12, 7))
        axs = axs.ravel()
    else:
        fig = None
    for ax, c in zip(axs, cols):
        if c not in feat.columns:
            ax.set_visible(False)
            continue
        ax.scatter(feat[c], feat["facility_kw"], s=6, alpha=0.25, c="#4C78A8")
        r = float(np.corrcoef(feat[c].to_numpy(dtype=float), feat["facility_kw"].to_numpy(dtype=float))[0, 1])
        lag_tag = "  [LAG]" if "lag" in c else ""
        ax.set_xlabel(c + lag_tag)
        ax.set_ylabel("facility_kw")
        ax.set_title(f"r={r:.3f}", fontsize=10)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    return fig


def lag_dependence_panel(
    y: np.ndarray,
    X: np.ndarray,
    feature_cols: list[str],
    peak: np.ndarray | None = None,
    ax=None,
):
    """Show how much lag1 alone explains vs full model context (corr + MAE)."""
    ax = ax or plt.gca()
    lag1_i = feature_cols.index("facility_kw_lag1")
    lag1 = X[:, lag1_i]
    persist_mae = float(mean_absolute_error(y, lag1))
    persist_r2 = float(r2_score(y, lag1))
    rows = [("all hours", persist_mae, persist_r2)]
    if peak is not None and np.any(peak):
        rows.append(
            (
                "peak HE 05–09",
                float(mean_absolute_error(y[peak], lag1[peak])),
                float(r2_score(y[peak], lag1[peak])),
            )
        )
    labels = [r[0] for r in rows]
    maes = [r[1] for r in rows]
    ax.bar(labels, maes, color=["#4C78A8", "#F58518"][: len(labels)])
    ax.set_ylabel("Persistence MAE (lag1 as prediction) [kW]")
    ax.set_title(
        f"Lag features in use: facility_kw_lag1/2 · oat_lag1\n"
        f"lag1 alone R²(all)={persist_r2:.3f} — strong autoregression; "
        f"champion must beat this on morning peak"
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def torch_family_mae_bars(cv: dict[str, dict[str, float]], ax=None):
    ax = ax or plt.gca()
    names = list(cv.keys())
    maes = [float(cv[n]["mae_peak_05_09"]) for n in names]
    order = np.argsort(maes)
    names = [names[i] for i in order]
    maes = [maes[i] for i in order]
    ax.barh(names, maes, color="#4C78A8")
    ax.set_xlabel("OOF morning-peak MAE [kW]")
    ax.set_title("PyTorch architecture bake-off (peak HE 05–09)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def multitarget_mae_rmse_bars(
    per_target: dict[str, dict[str, float]],
    ax=None,
):
    """Grouped MAE/RMSE bars for facility_kw + zone temps."""
    ax = ax or plt.gca()
    names = list(per_target.keys())
    mae = [float(per_target[n].get("mae", 0.0)) for n in names]
    rmse = [float(per_target[n].get("rmse", 0.0)) for n in names]
    y = np.arange(len(names))
    h = 0.38
    ax.barh(y - h / 2, mae, h, label="MAE", color="#4C78A8")
    ax.barh(y + h / 2, rmse, h, label="RMSE", color="#F58518")
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("Error")
    ax.set_title("Multi-target OOF errors (facility_kW + zone temps)")
    ax.legend(frameon=False, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def walk_24h_kw_and_temps(
    walk: dict[str, Any],
    *,
    occ_sp_f: float = 68.0,
    axs=None,
):
    """Plot 24h facility kW + 6 zone temps from a multitarget walk result."""
    if axs is None:
        fig, axs = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    else:
        fig = None
    hours = walk["hour_ending"]
    axs[0].plot(hours, walk["facility_kw"], color="#E45756", lw=2.2, label="facility_kW")
    axs[0].plot(hours, walk["oat_f"], color="#4C78A8", lw=1.4, ls="--", label="OAT °F")
    axs[0].set_ylabel("kW / °F")
    axs[0].set_title(f"24h forecast walk — {walk.get('strategy_id', '')}")
    axs[0].legend(frameon=False, fontsize=8)
    axs[0].spines["top"].set_visible(False)
    axs[0].spines["right"].set_visible(False)

    zt = walk["zone_temps"]
    cols = walk.get("zone_temp_cols", [f"z{i}" for i in range(zt.shape[1])])
    for i, name in enumerate(cols):
        axs[1].plot(hours, zt[:, i], lw=1.6, label=name.replace("zone_temp_", "").replace("_f", ""))
    axs[1].axhline(occ_sp_f, color="#54A24B", ls=":", lw=1.5, label=f"occ SP {occ_sp_f:.0f}°F")
    axs[1].axvline(7, color="#B279A2", ls="--", lw=1.2, label="HE 07 start")
    axs[1].set_xlabel("Hour local")
    axs[1].set_ylabel("Zone temp °F")
    axs[1].legend(frameon=False, fontsize=7, ncol=3)
    axs[1].spines["top"].set_visible(False)
    axs[1].spines["right"].set_visible(False)
    return fig


def warm_by_start_table(walk: dict[str, Any], occ_sp_f: float = 68.0) -> pd.DataFrame:
    flags = walk.get("warm_by_start") or {}
    cols = walk.get("zone_temp_cols") or list(flags.keys())
    rows = []
    for i, k in enumerate(cols):
        short = str(k).replace("zone_temp_", "").replace("_f", "")
        t7 = float(walk["zone_temps"][7, i])
        rows.append(
            {
                "zone": short,
                "temp_HE07_f": t7,
                "occ_sp_f": occ_sp_f,
                "warm_by_start": bool(flags.get(k, t7 >= occ_sp_f)),
            }
        )
    return pd.DataFrame(rows)


def feature_target_catalogs(*, multitarget: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Human-readable explainer + target dictionaries (blog / Kaggle style)."""
    from feature_compile_heating_dsm import (
        FEATURE_COLS,
        FEATURE_COLS_MULTITARGET,
        TARGET_COL,
        TARGET_COLS,
        ZONE_TEMP_COLS,
    )

    feat_desc = {
        "hour_ending": "Hour-ending clock (0–23 local)",
        "sin_hour": "Cyclical hour (sin)",
        "cos_hour": "Cyclical hour (cos)",
        "month": "Calendar month",
        "doy": "Day of year",
        "is_weekend": "Weekend flag (0/1)",
        "occupied": "Occupied flag (generic K12 07–16)",
        "oat_f": "Outdoor air temperature °F",
        "oat_lag1": "Prior-hour OAT °F (LAG — no future leak)",
        "hdd65": "Heating degree hours base 65°F",
        "hdd65_cum_night": "Cumulative night HDD (overnight recovery)",
        "hours_to_occupy": "Hours until school start",
        "rh_pct": "Relative humidity %",
        "ghi": "Global horizontal irradiance",
        "sum_occ_frac": "Sum of 6-Area occupancy fractions",
        "sum_hp_on": "Count of zones with HP/IdealLoads on",
        "preheat_lead_h": "Preheat lead time [h]",
        "stagger_min": "Stagger between Areas [min]",
        "unocc_htg_sp_f": "Unoccupied heating SP °F",
        "occ_htg_sp_f": "Occupied heating SP °F",
        "facility_kw_lag1": "Prior-hour facility kW (LAG — no future leak)",
        "facility_kw_lag2": "Two-hour lag facility kW (LAG)",
    }
    for z in ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B"):
        feat_desc[f"occ_frac_{z}"] = f"Occupancy fraction Area {z}"
        feat_desc[f"hp_on_{z}"] = f"HP / IdealLoads available Area {z} (desktop toggle)"
        feat_desc[f"zone_temp_{z}_f_lag1"] = f"Prior-hour zone temp Area {z} °F (LAG)"
    for s in (
        "baseline",
        "stagger_preheat",
        "flat_24_7",
        "deep_setback",
        "morning_all_on",
    ):
        feat_desc[f"strategy_{s}"] = f"One-hot strategy = {s}"

    cols = FEATURE_COLS_MULTITARGET if multitarget else FEATURE_COLS
    feat_rows = []
    for c in cols:
        role = "explainer (LAG)" if "lag" in c else "explainer"
        feat_rows.append({"feature": c, "role": role, "description": feat_desc.get(c, "")})

    if multitarget:
        tgt_rows = [
            {
                "target": TARGET_COL,
                "role": "prediction",
                "description": "Whole-building electric demand [kW] — primary DSM / cost metric",
            }
        ]
        for c in ZONE_TEMP_COLS:
            short = c.replace("zone_temp_", "").replace("_f", "")
            tgt_rows.append(
                {
                    "target": c,
                    "role": "prediction",
                    "description": f"Zone air temp Area {short} °F (warm-by-start)",
                }
            )
    else:
        tgt_rows = [
            {
                "target": TARGET_COL,
                "role": "prediction",
                "description": "Whole-building electric demand [kW] — primary DSM / cost metric",
            }
        ]
    return pd.DataFrame(feat_rows), pd.DataFrame(tgt_rows)


def save_fig(path: Path, fig=None, dpi: int = 140) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = fig or plt.gcf()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path
