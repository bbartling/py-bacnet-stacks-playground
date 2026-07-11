# Custom FDD rules (agent boilerplate)

**Where to look**

| Path | Role |
| --- | --- |
| [`app/rules/custom_boilerplate.py`](../../app/rules/custom_boilerplate.py) | Templates + helpers + worked examples (SAT high, rolling z-score “ML”) |
| [`app/rules/custom_rules.py`](../../app/rules/custom_rules.py) | **Agent edit surface** — append finished rules to `CUSTOM_RULES` |
| [`app/rules/custom_registry.py`](../../app/rules/custom_registry.py) | Merges custom into active catalog |
| Canonical 50 | [`app/rules/cookbook_catalog.py`](../../app/rules/cookbook_catalog.py) — do not silently omit |

## Agent workflow

1. Read `custom_boilerplate.py` docstring + examples.
2. Copy an example into `custom_rules.py` (or call `make_custom_rule(...)`).
3. Rule id **must** start with `CUSTOM-`.
4. `compute(df, params, poll) -> bool Series` aligned to `df.index`.
5. Include `CONFIRM_PARAM()` (0–60 min, default 5).
6. Optional: gate in `operational_gate.py` under the same id.
7. Test: `pytest tests/test_custom_rules.py -q`
8. Load package / run via Streamlit or `scripts/agent_afdd.py`.

Enable boilerplate examples without editing `custom_rules.py`:

```powershell
$env:VIBE19_INCLUDE_EXAMPLE_CUSTOM_RULES = "1"
streamlit run streamlit_app.py
```

## Rule shape (pandas)

```python
from app.rules.custom_boilerplate import make_custom_rule
from app.rules.cookbook_catalog import CookbookParam
from app.rules.custom_rules import CUSTOM_RULES  # edit the list in that module

def compute_my_fault(d, p, poll):
    sat = pd.to_numeric(d["sat"], errors="coerce")
    return sat.notna() & (sat > float(p.get("sat_hi", 75)))

CUSTOM_RULES.append(
    make_custom_rule(
        rule_id="CUSTOM-MY-FAULT",
        title="My site-specific fault",
        compute=compute_my_fault,
        required_roles=["sat"],
        equation="SAT > sat_hi",
        equipment_kinds=["ahu"],
        extra_params=[CookbookParam("sat_hi", "SAT high", "°F", 55, 120, 1, 75)],
    )
)
```

## Basic ML note

`CUSTOM-ZSCORE` is a rolling z-score anomaly (no sklearn). For IsolationForest / regressors, keep the same `CookbookRule` wrapper and only swap the `compute` body — add deps only if the deploy environment allows (Cloud `requirements.txt`).

## Canonical vs custom

- `CANONICAL_RULE_COUNT` stays **50**.
- Active `RULES` = canonical + `CUSTOM_*`.
- Never reuse a canonical id for a custom rule.
