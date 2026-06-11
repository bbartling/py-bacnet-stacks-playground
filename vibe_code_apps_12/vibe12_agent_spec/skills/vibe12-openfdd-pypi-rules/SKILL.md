---
name: vibe12-openfdd-pypi-rules
description: >-
  Open-FDD PyPI Arrow rules for Vibe12 cloud demo. Use when editing
  rules_defaults.py, brick_fdd_runner.py, or Arrow Rule Lab. Contract:
  apply_faults_arrow(table, cfg, context=None). Do not copy Open-FDD cookbook
  into this repo — link https://bbartling.github.io/open-fdd/rule-cookbook/
---

# Vibe12 Open-FDD PyPI rules

- FDD runtime: `pip install open-fdd` (pin in `fdd_lambda/requirements.txt` + SAM `OpenFddVersion`).
- Shipped pack: `vibe12_openfdd_cloud_demo_v1` in `aws_cloud_pipeline/fdd_lambda/rules_defaults.py`.
- Legacy row `evaluate(row, cfg)` is **not** supported.
- Local redirect only: `aws_cloud_pipeline/OPEN_FDD_RULES.md`.
