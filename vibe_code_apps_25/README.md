# Vibe 25 — Open-FDD PID hunting tutorial

Jupyter walkthrough of **PID-HUNT-1** from [`open-fdd`](https://pypi.org/project/open-fdd/) (pandas oracle): generate synthetic cooling-valve AO traces, learn the rolling TV / span / cycles / reversals math, run `hunting_fault_mask`, and plot how those metrics AND into a fault.

This is a **screening** demo — suspected control-output hunting, not proof of a bad PID alone. Distinct from cookbook **FC4** (operating-state oscillation).

## Quick start

```powershell
cd vibe_code_apps_25
pip install -e ".[dev]"
jupyter notebook notebooks/01_pid_hunt_tutorial.ipynb
```

Or execute headlessly:

```powershell
jupyter nbconvert --to notebook --execute notebooks/01_pid_hunt_tutorial.ipynb --inplace
python -m pytest
```

Optional tip-of-tree Open-FDD:

```powershell
pip install -e "C:\Users\ben\Documents\open-fdd[oracle]"
```

## Layout

| Path | Role |
|------|------|
| [`notebooks/01_pid_hunt_tutorial.ipynb`](notebooks/01_pid_hunt_tutorial.ipynb) | Tutorial |
| [`src/vibe25/synth.py`](src/vibe25/synth.py) | Healthy vs hunting AO generators |
| [`tests/`](tests/) | Detector smoke tests |

## Defaults (Open-FDD `PidHuntingParams`)

Rolling **1h** window; fault when coverage ≥ 80%, span ≥ 20%, TV ≥ 500 %-pts, equivalent cycles ≥ 2.5, and reversals ≥ 4.
