# Vibe22 RL proof-of-concept blog pack

This pack separates the publishable proof of concept from claims the present evidence cannot support.

## Contents

- [`vibe22-rl-proof-of-concept-blog-outline.md`](vibe22-rl-proof-of-concept-blog-outline.md)
- [`build_source_backed_figures.py`](build_source_backed_figures.py)
- `figures/01`–`03`: SVG schematics plus PNG
- `figures/04`: Jan 26 paired EnergyPlus control sensitivity (not RL)
- `figures/05`: BAS vs A04 zone-ramp honesty check
- `data/`: committed 96-row scored pair parquets

## Claim

Five valid post-fix EnergyPlus gate calls prove the daily six-zone simulator responds to controls. Valid post-fix PPO/DQN training episodes remain zero.

## Regenerate source-backed figures

```powershell
python vibe_code_apps_22/docs/blog/2026-08-15-rl-poc/build_source_backed_figures.py `
  --vibe22-root vibe_code_apps_22 `
  --site-root "<SITE_ROOT>"
```

`--vibe22-root` and `--site-root` are required. Generated JSON/PNG payloads do not embed those paths. Pair CSVs/parquets in `data/` are scored 96-row files only (not full E+ trees).

The script does not run EnergyPlus or train RL.
