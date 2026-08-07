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


def torch_family_mae_bars(cv: dict[str, dict[str, float]], ax=None, title: str | None = None):
    ax = ax or plt.gca()
    names = list(cv.keys())
    maes = [float(cv[n]["mae_peak_05_09"]) for n in names]
    order = np.argsort(maes)
    names = [names[i] for i in order]
    maes = [maes[i] for i in order]
    ax.barh(names, maes, color="#4C78A8")
    ax.set_xlabel("OOF morning-peak MAE [kW]")
    ax.set_title(title or "PyTorch architecture bake-off (peak HE 05–09)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def family_mae_bars(
    cv: dict[str, dict[str, float]],
    ax=None,
    *,
    title: str = "Family bake-off (peak HE 05–09)",
    highlight: str | None = None,
):
    """Horizontal peak-MAE bars for any family dict (CatBoost / Torch / sklearn)."""
    ax = ax or plt.gca()
    names = list(cv.keys())
    maes = [float(cv[n]["mae_peak_05_09"]) for n in names]
    order = np.argsort(maes)
    names = [names[i] for i in order]
    maes = [maes[i] for i in order]
    colors = ["#F58518" if highlight and n == highlight else "#4C78A8" for n in names]
    ax.barh(names, maes, color=colors)
    ax.set_xlabel("OOF morning-peak MAE [kW]")
    ax.set_title(title)
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
    try:
        from IPython.display import display

        display(fig)
    except Exception:
        pass
    return path


# ---------------------------------------------------------------------------
# Tutorial-quality multi-output visualizations
# ---------------------------------------------------------------------------

_STYLE = {
    "actual": "#264653",
    "pred": "#e76f51",
    "baseline": "#2a9d8f",
    "hybrid": "#e9c46a",
    "comfort": "#e63946",
}


def coverage_timeline(df: pd.DataFrame, ax=None, *, day_col: str = "day"):
    """Show available calendar coverage (one mark per day)."""
    ax = ax or plt.gca()
    days = pd.to_datetime(sorted(df[day_col].astype(str).unique()))
    ax.scatter(days, np.ones(len(days)), s=18, c=_STYLE["baseline"], marker="|")
    ax.set_yticks([])
    ax.set_xlabel("Calendar day")
    ax.set_title(f"Available training days (n={len(days)} independent days)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    return ax


def missingness_summary(df: pd.DataFrame, cols: list[str], ax=None):
    ax = ax or plt.gca()
    rates = [float(df[c].isna().mean()) if c in df.columns else 1.0 for c in cols]
    ax.barh(cols[::-1], rates[::-1], color="#457b9d")
    ax.set_xlabel("Fraction missing")
    ax.set_title("Missingness summary (descriptive)")
    ax.set_xlim(0, max(0.05, max(rates) * 1.1 if rates else 0.05))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def target_distributions(df: pd.DataFrame, *, target_cols: list[str] | None = None, fig=None):
    from feature_compile_heating_dsm import TARGET_COLS

    cols = target_cols or list(TARGET_COLS)
    fig = fig or plt.figure(figsize=(12, 8))
    axes = fig.subplots(3, 3)
    axes = axes.ravel()
    for i, c in enumerate(cols):
        ax = axes[i]
        if c in df.columns:
            ax.hist(df[c].dropna(), bins=40, color="#4C78A8", alpha=0.85)
        unit = "kW" if c == "facility_kw" else "°F"
        ax.set_title(c)
        ax.set_xlabel(unit)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    for j in range(len(cols), len(axes)):
        axes[j].axis("off")
    fig.suptitle("Target distributions (facility kW + six thermal-area temps)", y=1.01)
    fig.tight_layout()
    return fig


def winter_day_panel(df: pd.DataFrame, day: str, *, fig=None):
    """OAT + facility kW + six zone temps for one example winter day."""
    from feature_compile_heating_dsm import ZONE_TEMP_COLS

    sub = df[df["day"].astype(str) == str(day)].sort_values(
        "step_15" if "step_15" in df.columns else "hour_ending"
    )
    fig = fig or plt.figure(figsize=(11, 8))
    ax0 = fig.add_subplot(3, 1, 1)
    x = sub["step_15"] / 4.0 if "step_15" in sub.columns else sub["hour_ending"]
    if "oat_f" in sub.columns:
        ax0.plot(x, sub["oat_f"], color="#1d3557", label="OAT")
    ax0.set_ylabel("OAT [°F]")
    ax0.set_title(f"Example winter day {day} — outdoor air, demand, zone temps")
    ax0.legend(frameon=False)
    ax0.spines["top"].set_visible(False)
    ax0.spines["right"].set_visible(False)

    ax1 = fig.add_subplot(3, 1, 2, sharex=ax0)
    if "facility_kw" in sub.columns:
        ax1.plot(x, sub["facility_kw"], color=_STYLE["pred"], label="facility_kw")
    ax1.set_ylabel("kW")
    ax1.legend(frameon=False)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    ax2 = fig.add_subplot(3, 1, 3, sharex=ax0)
    for zc in ZONE_TEMP_COLS:
        if zc in sub.columns:
            ax2.plot(x, sub[zc], lw=1.2, label=zc.replace("zone_temp_", "").replace("_f", ""))
    ax2.set_ylabel("Zone temp [°F]")
    ax2.set_xlabel("Hour of day")
    ax2.legend(fontsize=7, ncol=3, frameon=False)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


def descriptive_corr_heatmap(df: pd.DataFrame, cols: list[str], ax=None):
    ax = ax or plt.gca()
    sub = df[[c for c in cols if c in df.columns]].corr()
    im = ax.imshow(sub.values, cmap="coolwarm", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(sub.columns)))
    ax.set_yticks(range(len(sub.columns)))
    ax.set_xticklabels(sub.columns, rotation=45, ha="right", fontsize=7)
    ax.set_yticklabels(sub.columns, fontsize=7)
    ax.set_title("Correlation heatmap (descriptive — not causal)")
    plt.colorbar(im, ax=ax, fraction=0.046)
    return ax


def actual_vs_pred_timeseries(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    x=None,
    ylabel: str = "facility_kw [kW]",
    title: str = "Actual vs predicted",
    split_label: str = "validation",
    ax=None,
):
    ax = ax or plt.gca()
    yt = np.asarray(y_true, dtype=float).ravel()
    yp = np.asarray(y_pred, dtype=float).ravel()
    xx = np.arange(len(yt)) if x is None else np.asarray(x)
    ax.plot(xx, yt, color=_STYLE["actual"], lw=1.6, label="actual")
    ax.plot(xx, yp, color=_STYLE["pred"], lw=1.4, alpha=0.9, label="predicted")
    ax.set_ylabel(ylabel)
    ax.set_title(f"{title} ({split_label})")
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def residuals_by_hour(y_true, y_pred, hour_ending, ax=None):
    ax = ax or plt.gca()
    resid = np.asarray(y_true) - np.asarray(y_pred)
    he = np.asarray(hour_ending)
    means = [float(np.mean(resid[he == h])) if np.any(he == h) else np.nan for h in range(24)]
    ax.bar(range(24), means, color="#a8dadc", edgecolor="#1d3557")
    ax.axhline(0, color="#e63946", ls="--")
    ax.set_xlabel("Hour ending")
    ax.set_ylabel("Mean residual (actual − pred)")
    ax.set_title("Residuals by hour of day")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def residuals_vs_oat(y_true, y_pred, oat_f, ax=None):
    ax = ax or plt.gca()
    resid = np.asarray(y_true) - np.asarray(y_pred)
    ax.scatter(oat_f, resid, s=8, alpha=0.35, c="#457b9d")
    ax.axhline(0, color="#e63946", ls="--")
    ax.set_xlabel("OAT [°F]")
    ax.set_ylabel("Residual [kW]")
    ax.set_title("Residuals versus outdoor-air temperature")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def horizon_mae_plot(horizon_dict: dict[str, float], ax=None, *, ylabel: str = "MAE"):
    ax = ax or plt.gca()
    steps, vals = [], []
    for k, v in sorted(horizon_dict.items()):
        if "horizon_mae_step_" in k and v is not None:
            steps.append(int(k.rsplit("_", 1)[-1]))
            vals.append(float(v))
    ax.plot(steps, vals, marker="o", color=_STYLE["pred"])
    ax.set_xlabel("Forecast horizon (15-min step)")
    ax.set_ylabel(ylabel)
    ax.set_title("Recursive error by forecast horizon (step 1 → 96)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def zone_small_multiples(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    zone_names: list[str] | None = None,
    split_label: str = "validation",
    fig=None,
):
    from feature_compile_heating_dsm import ZONE_TEMP_COLS

    names = zone_names or [c.replace("zone_temp_", "").replace("_f", "") for c in ZONE_TEMP_COLS]
    yt = np.asarray(y_true)
    yp = np.asarray(y_pred)
    fig = fig or plt.figure(figsize=(12, 8))
    axes = fig.subplots(2, 3)
    for i, ax in enumerate(axes.ravel()):
        if i >= yt.shape[1]:
            ax.axis("off")
            continue
        ax.plot(yt[:, i], color=_STYLE["actual"], lw=1.0, label="actual")
        ax.plot(yp[:, i], color=_STYLE["pred"], lw=1.0, alpha=0.85, label="pred")
        ax.set_title(names[i])
        ax.set_ylabel("°F")
        if i == 0:
            ax.legend(fontsize=7, frameon=False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.suptitle(f"Zone temperatures — actual vs predicted ({split_label})")
    fig.tight_layout()
    return fig


def model_comparison_bars(rows: list[dict[str, Any]], metric: str, ax=None, *, ylabel: str | None = None):
    ax = ax or plt.gca()
    names = [r["model"] for r in rows]
    vals = [r.get(metric) for r in rows]
    ax.barh(names[::-1], vals[::-1], color="#2a9d8f")
    ax.set_xlabel(ylabel or metric)
    ax.set_title(f"Model comparison — {metric} (lower is better)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def pareto_peak_vs_worst_zone(rows: list[dict[str, Any]], ax=None):
    ax = ax or plt.gca()
    for r in rows:
        ax.scatter(
            r.get("facility_peak_mae"),
            r.get("worst_zone_mae"),
            s=60,
            label=r["model"],
        )
        ax.annotate(r["model"], (r.get("facility_peak_mae"), r.get("worst_zone_mae")), fontsize=7)
    ax.set_xlabel("Facility morning-peak MAE [kW]")
    ax.set_ylabel("Worst-zone temperature MAE [°F]")
    ax.set_title("Pareto: peak demand error vs worst-zone temp error")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def hybrid_walk_panel(walk: dict[str, Any], *, fig=None, comfort_sp: float = 68.0, comfort_band: float = 2.0):
    """Baseline vs hybrid facility kW + zone temps with comfort bounds."""
    steps = walk.get("steps") or []
    fig = fig or plt.figure(figsize=(11, 8))
    ax0 = fig.add_subplot(2, 1, 1)
    t = [s["step_15"] / 4.0 for s in steps]
    ax0.plot(t, [s["baseline_facility_kw"] for s in steps], color=_STYLE["baseline"], label="baseline")
    ax0.plot(t, [s["hybrid_facility_kw"] for s in steps], color=_STYLE["hybrid"], label="hybrid DSM")
    ax0.axvspan(5, 9, color="#f4a261", alpha=0.15, label="morning peak HE 05–09")
    ax0.set_ylabel("facility_kw [kW]")
    ax0.set_title("Hybrid DSM walk — predicted baseline vs hybrid (not measured actual)")
    ax0.legend(frameon=False, fontsize=8)
    ax0.spines["top"].set_visible(False)
    ax0.spines["right"].set_visible(False)

    ax1 = fig.add_subplot(2, 1, 2, sharex=ax0)
    lo = comfort_sp - comfort_band
    for s in steps:
        hz = s.get("hybrid_zone_temps_f") or {}
        break
    zone_keys = list((steps[0].get("hybrid_zone_temps_f") or {}).keys()) if steps else []
    for zk in zone_keys:
        ax1.plot(t, [s.get("hybrid_zone_temps_f", {}).get(zk, np.nan) for s in steps], lw=1.0, label=zk)
    ax1.axhline(lo, color=_STYLE["comfort"], ls="--", label=f"comfort_lo {lo:.0f}°F")
    ax1.set_ylabel("Zone temp [°F]")
    ax1.set_xlabel("Hour of day")
    ax1.legend(fontsize=6, ncol=3, frameon=False)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


def typical_weekday_weekend_profile(demand: pd.DataFrame, *, kw_col: str = "kw_demand", ax=None):
    """Mean diurnal kW for weekday vs weekend (expects hour + is_weekend or day_type)."""
    ax = ax or plt.gca()
    df = demand.copy()
    if "hour" not in df.columns and "ts_local" in df.columns:
        df["hour"] = pd.to_datetime(df["ts_local"]).dt.hour
    if "day_type" not in df.columns:
        if "is_weekend" in df.columns:
            df["day_type"] = np.where(df["is_weekend"], "Weekend", "Weekday")
        else:
            raise ValueError("need day_type or is_weekend")
    for day_type, color in (("Weekday", _STYLE["baseline"]), ("Weekend", _STYLE["pred"])):
        sub = df[df["day_type"] == day_type]
        if sub.empty:
            continue
        g = sub.groupby("hour")[kw_col].mean().sort_index()
        ax.plot(g.index, g.values, lw=2.0, color=color, label=day_type)
        ax.fill_between(g.index, g.values, alpha=0.12, color=color)
    ax.set_xlabel("Hour (local)")
    ax.set_ylabel("Mean demand [kW]")
    ax.set_title("Typical load shape — weekday vs weekend (meter)")
    ax.set_xlim(0, 23)
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def monthly_diurnal_overlay(demand: pd.DataFrame, *, kw_col: str = "kw_demand", fig=None):
    """One small panel per month: weekday vs weekend mean kW by hour."""
    df = demand.copy()
    if "month" not in df.columns and "ts_local" in df.columns:
        df["month"] = pd.to_datetime(df["ts_local"]).dt.to_period("M").astype(str)
    if "hour" not in df.columns and "ts_local" in df.columns:
        df["hour"] = pd.to_datetime(df["ts_local"]).dt.hour
    if "day_type" not in df.columns and "is_weekend" in df.columns:
        df["day_type"] = np.where(df["is_weekend"], "Weekend", "Weekday")
    months = sorted(df["month"].dropna().unique())
    ncols = 3
    nrows = int(np.ceil(max(1, len(months)) / ncols))
    fig = fig or plt.figure(figsize=(12, 3.0 * nrows))
    axes = fig.subplots(nrows, ncols, sharey=True)
    axes = np.atleast_1d(axes).ravel()
    for i, month in enumerate(months):
        ax = axes[i]
        sub = df[df["month"] == month]
        for day_type, color in (("Weekday", _STYLE["baseline"]), ("Weekend", _STYLE["pred"])):
            s = sub[sub["day_type"] == day_type]
            if s.empty:
                continue
            g = s.groupby("hour")[kw_col].mean().sort_index()
            ax.plot(g.index, g.values, color=color, lw=1.6, label=day_type)
        ax.set_title(str(month), fontsize=10)
        ax.set_xlim(0, 23)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if i == 0:
            ax.legend(fontsize=7, frameon=False)
    for j in range(len(months), len(axes)):
        axes[j].axis("off")
    fig.suptitle("Monthly diurnal shapes — weekday vs weekend (meter)")
    fig.tight_layout()
    return fig


def actual_eplus_ml_overlay(
    *,
    hour: np.ndarray | list,
    actual_kw: np.ndarray | list | None = None,
    eplus_kw: np.ndarray | list | None = None,
    ml_baseline_kw: np.ndarray | list | None = None,
    ml_hybrid_kw: np.ndarray | list | None = None,
    title: str = "Load profile overlay — Actual vs E+ vs ML",
    ax=None,
):
    """Overlay diurnal kW series. Never label ML hybrid as actual."""
    ax = ax or plt.gca()
    x = np.asarray(hour, dtype=float)
    if actual_kw is not None:
        ax.plot(x, actual_kw, color=_STYLE["actual"], lw=2.0, label="Actual meter / BAS")
    if eplus_kw is not None:
        ax.plot(x, eplus_kw, color="#457b9d", lw=1.6, ls="--", label="EnergyPlus (IdealLoads screening)")
    if ml_baseline_kw is not None:
        ax.plot(x, ml_baseline_kw, color=_STYLE["baseline"], lw=1.6, label="ML baseline (predicted)")
    if ml_hybrid_kw is not None:
        ax.plot(x, ml_hybrid_kw, color=_STYLE["hybrid"], lw=1.8, label="ML hybrid DSM (predicted, not actual)")
    ax.axvspan(5, 9, color="#f4a261", alpha=0.12, label="morning peak HE 05–09")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("facility_kw [kW]")
    ax.set_title(title)
    ax.legend(frameon=False, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax
