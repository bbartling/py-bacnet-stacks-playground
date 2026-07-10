# Make your own CSV FDD Streamlit demo

App 19 is a **reusable template**, not a single-building product. The code in this repo is the pattern; **your CSV tree + role map + rule tunables** are the deliverable.

`BUILDING_100` and `BUILDING_50` are **reference examples** used to develop and test the template. They are not shipped in git — browse your own local building folder.

---

## What you keep vs change

| Layer | Usually keep (template) | You customize |
| --- | --- | --- |
| Data layout | [`DATA_CONTRACT.md`](DATA_CONTRACT.md) | Your `DATA_ROOT`, building id, equipment folders |
| Validation | `validate_data.py`, `shared/data_config.py` | Fix gaps until GO |
| Rules | `app/rules/cookbook_catalog.py` + runner | Thresholds, which equipment types apply |
| Role map | `app/role_map.py` + mapping wizard | Point → cookbook role columns |
| UI | `streamlit_app.py` | Title, copy, default confirm delay |
| Charts | `app/charts.py` + **RCx Plots** tab | Series selection / units / presets |
| Weather | `app/weather_psychrometrics.py` + `weather/` CSV | Web OAT / RH → dewpoint & wet-bulb |

---

## Greenfield workflow (any site)

1. **Export CSV tree** — Open-FDD sidecar or compatible wide history (see [Open-FDD CSV import](https://bbartling.github.io/open-fdd/drivers/csv-batch-import/))
2. **Set paths** — copy `.env.example` → `.env` with `HVAC_DATA_ROOT` + `HVAC_BUILDING`, or use `data_paths.local.yaml`
3. **Validate** — `python validate_data.py` until GO
4. **Map points** — Streamlit mapping wizard / `configs/role_map.yaml` (`oa_t`, `mat`, `fan_cmd`, …)
5. **Run** — `streamlit run streamlit_app.py` → Run rules → Overview / Analytics / Plots
6. **Tune** — sidebar confirm delay + rule defaults; see [`docs/RULE_TUNING_GUIDE.md`](../docs/RULE_TUNING_GUIDE.md)

---

## Generic code rules (for agents & forks)

1. **Never hardcode** a customer building name, path, AHU count, or poll interval in committed Python
2. **Building id = folder name** — any site label
3. **Tests use synthetic fixtures** — no client CSV in git
4. **Do not recreate** retired stacks (`haystack_rdf/`, `fdd_app/`, FastAPI static HTML)

---

## Fork checklist

- [ ] Own `DATA_ROOT` validates GO
- [ ] Role map covers AHUs / VAVs / plant you care about
- [ ] `python -m pytest -q` green
- [ ] Streamlit run shows 50 rules with no `ERROR` rows on your sample window
