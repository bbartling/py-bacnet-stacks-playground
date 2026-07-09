# Rule tuning guide

Sliders are defined in `configs/rule_defaults.yaml`. Each rule block maps to a `config_key` in `app/rules/__init__.py`.

## Workflow

1. Load data (BUILDING_100 or upload)
2. Map roles in **Role Mapping**
3. Adjust sliders in sidebar expanders
4. **Rule Tuning** tab → Run selected rules
5. Review **Fault Results** and **Trends**
6. Add engineer notes in sidebar text areas (included in export)

## Reset

Click **Reset sliders to defaults** in the sidebar.

## Confirm time

`confirm_minutes` × 60 → `confirm_seconds` passed to `confirm_fault()` (Open-FDD-style streak logic).

## Parameters by rule

| Rule | Key params |
| --- | --- |
| VAV-1 | `low_limit_f`, `high_limit_f`, `confirm_minutes` |
| SAT-HIGH | `sat_high_delta_f`, `confirm_minutes` |
| ECON-2 | `oat_hi_f`, `damper_frac`, `confirm_minutes` |
| OAT-METEO | `oat_err_f`, `confirm_minutes` (needs weather) |

Edit YAML to add new slider metadata — no code change required for min/max/step defaults.
