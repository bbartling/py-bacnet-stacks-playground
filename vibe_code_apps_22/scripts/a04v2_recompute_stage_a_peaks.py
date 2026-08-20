"""Recompute Stage A incumbent peaks under 5/15/30/60-min windows. Does not delete Stage A."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.demand_windows import demand_window_report, freeze_peak_contract
from eplus_gym.objective import _facility_series


def main() -> int:
    root = _APP / "docs" / "audits" / "figures" / "a04v2"
    contract = freeze_peak_contract()
    (root / "peak_contract.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    rows = []
    stage_a = root / "stageA"
    if stage_a.is_dir():
        for trial in sorted(p for p in stage_a.iterdir() if p.is_dir()):
            traj = trial / "incumbent" / "trajectory.parquet"
            if not traj.is_file():
                continue
            df = pd.read_parquet(traj)
            fac = _facility_series(df)
            if "timestamp" in df.columns:
                idx = pd.to_datetime(df["timestamp"])
            elif "local_step" in df.columns:
                idx = pd.date_range("2026-01-26", periods=len(fac), freq="15min")
            else:
                idx = pd.date_range("2026-01-26", periods=len(fac), freq="15min")
            series = pd.Series(fac.to_numpy(), index=pd.DatetimeIndex(idx[: len(fac)]))
            rep = demand_window_report(series, native_minutes=15)
            rows.append({"run_id": trial.name, **{k: rep[k] for k in ("native_max_kw", "aligned_max_kw", "rolling_max_kw")}})
    out = {"schema": "vibe22.a04v2.stageA_peak_windows.v1", "peak_contract": contract, "trials": rows}
    (root / "stageA_peak_windows.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n_trials": len(rows), "contract_hard_gate": contract["hard_gate_on_15min_vs_billed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
