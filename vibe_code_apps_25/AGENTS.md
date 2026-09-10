# AGENTS.md — Vibe 25 Open-FDD PID hunting tutorial

**Mission:** teach **PID-HUNT-1** (suspected control-output hunting) with synthetic AO data and the Open-FDD pandas detector.

**Claim boundary:** educational screening demo. PID-HUNT-1 is **suspected loop hunting**, not proof of bad PID alone. Do not invent thresholds — use `PidHuntingParams` defaults from Open-FDD.

## Install
```powershell
cd vibe_code_apps_25
pip install -e ".[dev]"
# tip-of-tree Open-FDD (optional):
# pip install -e "C:\Users\ben\Documents\open-fdd[oracle]"
```

PyPI package is **`open-fdd`** (import `open_fdd`). Extra **`[oracle]`** pulls pandas rules.

## Hard rules
- Tutorial scope is **PID-HUNT-1** (AO TV / span / cycles / reversals) — **not** FC4 (AHU operating-state thrash)
- Extreme low/high seen metrics are diagnostic only — they are **not** in the fault AND
- Keep synth generators deterministic (`vibe25.synth`) so pytest stays green
- Prefer column roles like `cooling-valve` with a `DatetimeIndex`

## Resume
```powershell
python -m pytest
python -m ruff check src tests
jupyter notebook notebooks/01_pid_hunt_tutorial.ipynb
```
