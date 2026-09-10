# Vibe 25 — Open-FDD PID hunting tutorial

For **controls technicians**: is a cooling valve settling, or hunting?

Jupyter walkthrough of Open-FDD **PID-HUNT-1** with synthetic sine-wave AO data, plain-English TV/span explanation, and zoomed cycle callouts. Helper code is in importable Python modules (`vibe25.synth`, `vibe25.detect`, `vibe25.plotting`).

## Quick start

```powershell
cd vibe_code_apps_25
pip install -e ".[dev]"
jupyter notebook notebooks/01_pid_hunt_tutorial.ipynb
```

## Layout

| Path | Role |
|------|------|
| [`notebooks/01_pid_hunt_tutorial.ipynb`](notebooks/01_pid_hunt_tutorial.ipynb) | Short tech-facing tutorial |
| [`src/vibe25/synth.py`](src/vibe25/synth.py) | Healthy + hunting generators |
| [`src/vibe25/detect.py`](src/vibe25/detect.py) | `run_pid_hunt` wrapper |
| [`src/vibe25/plotting.py`](src/vibe25/plotting.py) | Overview + TV zoom plots |

Screening demo only — not proof of bad PID alone.
