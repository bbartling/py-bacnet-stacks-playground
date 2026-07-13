---
name: vibe19-pandas-fdd-rules
description: >-
  Use when implementing HVAC fault rules in pandas for App 19 with Open-FDD cookbook
  parity: confirm_fault, poll_seconds, operational gates, ECON free-cool (web weather),
  VAV fixed flow, CW wet-bulb. Triggers on: FDD, fault, rule, cookbook, confirm_fault,
  economizer, ECON-3, VAV-7, CW-OPT, OAT-METEO, pandas rule.
---

# Vibe19 — Pandas FDD rules (Open-FDD parity)

## Primary reference

[Pandas FDD Cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html)

Also: [`docs/OPENFDD_PARITY.md`](../docs/OPENFDD_PARITY.md) · [`docs/OPERATIONAL_GATES.md`](../docs/OPERATIONAL_GATES.md)

## Standard rule pipeline

```python
# 1. raw mask from cookbook
raw = ...  # boolean Series aligned to d.index

# 2. operational gate — AND with active_mask (prefer fan_status over fan_cmd)
#    If gate applied and zero active samples → SKIPPED_EQUIPMENT_OFF

# 3. confirm
confirmed = confirm_fault(raw & active, poll_seconds=p["poll_seconds"])

# 4. rollup hours / pct using **active** samples as denominator when gated
```

Statuses: `PASS` | `FAULT` | `SKIPPED_MISSING_ROLES` | `SKIPPED_EQUIPMENT_OFF` | `NOT_APPLICABLE_EQUIPMENT_TYPE` | `ERROR`

## Weather / free cooling

- Weather CSV enriched in `app/weather_psychrometrics.py` → `wx_oa_t`, `wx_oa_rh`, `wx_oa_dewpoint`, `wx_oa_wetbulb`
- **ECON-3** (`runner.econ3_compute`): free cool when **web** dry-bulb in band (default 35–72°F) AND dewpoint &lt; 60°F (derive from RH if needed); fault when mech cooling with damper closed; optional SAT≈SP (“keeping up”)
- **OAT-METEO**: `|oa_t − wx_oa_t| > oat_err` (default 5°F, slider)
- **CW-OPT-1**: CW supply colder than wet-bulb + approach (Stull) — replaced WX-2

## Notable rule enhancements

| ID | Behavior |
| --- | --- |
| VAV-7 | Under min flow **or** fixed high flow (low rolling std + high mean) **or** high `min_flow_sp` |
| ECON-3 | Web OAT + dewpoint free-cool window |
| CW-OPT-1 | Condenser water vs wet-bulb optimization |

## Reference modules

| Module | Role |
| --- | --- |
| `app/rules/cookbook_catalog.py` | Canonical 50-rule definitions |
| `app/rules/runner.py` | Skip / gate / confirm / ECON-3 |
| `app/rules/base.py` | `confirm_fault`, `hours_true` |
| `app/rules/operational_gate.py` | `RULE_GATES` |
| `app/role_map.py` | Role aliases + `resolve_role()` |

After catalog edits: `python scripts/generate_rule_configs.py` then pytest.

## Param / algebra checklist (before shipping a rule or slider)

1. After writing `compute`, algebraically simplify: the declared param must still appear (no same-side cancel).
2. **FC2** envelope: `mat + ε < min(rat, oat) − ε` (≡ `mat < min − 2ε`). **FC3**: `mat − ε > max + ε`. **FC5**: apply `mix_tol` on both SAT and MAT sides.
3. Run `pytest tests/test_rule_param_sensitivity.py` (tight vs loose must change mask/status).
4. Do not confuse Plotly downsample (chart) with rule math — rules never smooth historian data.

## Custom / agent rules (boilerplate)

| Path | Role |
| --- | --- |
| `app/rules/custom_boilerplate.py` | Templates + SAT-high + rolling z-score examples |
| `app/rules/custom_rules.py` | Append agent `CUSTOM-*` rules here |
| `app/rules/custom_registry.py` | Merges into active `RULES` |
| `docs/CUSTOM_RULES.md` | Full agent how-to |

Ids must start with `CUSTOM-`. Canonical 50 stay intact. Env `VIBE19_INCLUDE_EXAMPLE_CUSTOM_RULES=1` loads examples without editing `custom_rules.py`.

## Tests

Synthetic DataFrames in `tests/` — **no client CSV in git**. Parity script: `scripts/csv_parity_check.py --building-folder …`.

Param-sensitivity: `tests/test_rule_param_sensitivity.py` (dead-slider / same-side tol cancel guard).
