# Open-FDD pandas parity (App 19)

App 19 implements the **[Pandas FDD Cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html)** offline in Streamlit. Production Open-FDD edge runs **Rust + DataFusion SQL** in a separate repo — do not re-add that stack here.

---

## Parity rules

| Concept | Open-FDD / cookbook | App 19 |
| --- | --- | --- |
| Poll interval | Historian sample period | `manifest.json` `grid_minutes` → `df.attrs["poll_seconds"]` |
| Fault confirm | Default **300 s** | `confirm_fault()` consecutive True rows |
| Raw vs confirmed | `fault_raw` → `fault_confirmed` | Same idea in `app/rules/base.py` |
| Prerequisites | Fan proven on, etc. | `app/rules/operational_gate.py` |
| Rollup | SQL window sums | `hours_true(mask, poll_seconds)` |
| Point keys | Sanitized / Haystack-like roles | YAML role map + `app/role_map.py` |
| Outdoor air | Open-Meteo / weather CSV | Prefer **`wx_oa_t`** (web) over BAS `oa_t` for analytics / ECON-3 |
| Dewpoint / wet-bulb | Historian or derived | Magnus dewpoint + Stull wet-bulb in `app/weather_psychrometrics.py` |

---

## Shared helpers

```python
from app.rules.base import confirm_fault, hours_true
```

Canonical catalog: `app/rules/cookbook_catalog.py` (53 rules). Inventory: [`../../docs/STREAMLIT_RULE_INVENTORY.md`](../../docs/STREAMLIT_RULE_INVENTORY.md). Per-rule plots / Haystack tags / sliders: [`RULE_PLOT_CATALOG.md`](RULE_PLOT_CATALOG.md).

---

## GL36 mixing / supply envelopes (FC2 / FC3 / FC5)

| Rule | Form (ε = `mix_tol`, default 1.15°F) |
| --- | --- |
| **FC2** | `mat + ε < min(rat, oat) − ε` ≡ `mat < min(rat, oat) − 2ε` |
| **FC3** | `mat − ε > max(rat, oat) + ε` ≡ `mat > max(rat, oat) + 2ε` |
| **FC5** | `sat + ε ≤ mat − ε + Δ_supply_fan` (ε on both SAT and MAT) |

Never write `(x − ε) < min(… − ε)` / `(x − ε) > max(… − ε)` — ε cancels and the sidebar slider is dead. Guard: `tests/test_rule_param_sensitivity.py`.

---

## Taxonomy & metadata

- [Public FDD taxonomy](https://bbartling.github.io/open-fdd/rules/cookbook/public-fdd-taxonomy.html)
- [P0 rule catalog](https://bbartling.github.io/open-fdd/rules/cookbook/p0-rule-catalog.html)

When adding a rule, record: rule id, confirm seconds, gate, required roles, equipment types. Append [`SESSION_LOG.md`](../SESSION_LOG.md).

---

## Parity testing workflow

1. Slice CSV to one AHU / one week
2. Run Streamlit rules → fault hour total
3. (Optional) Compare against Open-FDD SQL in the production repo on the same window
4. Document ± tolerance in pytest

Gap matrix: [Open-FDD gap matrix](https://bbartling.github.io/open-fdd/rules/cookbook/gap-matrix.html)
