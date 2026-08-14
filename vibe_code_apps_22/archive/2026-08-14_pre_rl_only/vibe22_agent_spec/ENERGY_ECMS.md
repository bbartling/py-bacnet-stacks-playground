# Energy ECMs (agent-driven)

Human Streamlit tab **Energy ECMs** is **view-only**. Agents assemble open-fdd
workbooks + staged EnergyPlus patches; the human refreshes the tab and chats
for revisions.

## Split from Run DSM

| Surface | Job |
| --- | --- |
| **Run DSM** | Peak / control strategies on the published W2A twin (closed-loop rules) |
| **Energy ECMs** | Annual / package screening: spreadsheet vs E+ (`ss_*` vs `ep_*`) |

Do not rank annual ECMs inside Run DSM.

## Workflow

```text
1. pip install open-fdd
2. from open_fdd.ecm_engineering import ECMJob
   job = ECMJob("Site").set_global(...).add_ecm(...)
   job.attach_twin_compare({...})   # optional honesty / E+ rows
   job.save("{SITE_ROOT}/reports/notebooks/Site_ECMs.xlsx")
3. Stage IDF patches + run EnergyPlus (EnergyPlus-MCP / campaign scripts).
   Never overwrite the published champion IDF.
4. Write {SITE_ROOT}/reports/ecm_compare.json via
   eplus_gym_app.ecm_publish.save_ecm_compare (or hand-shaped site_ecm_compare_v1).
5. Human opens Energy ECMs tab → chats with agent for revisions.
```

Helpers: [`eplus_gym_app/ecm_publish.py`](../eplus_gym_app/ecm_publish.py),
[`eplus_gym_app/ecm_panel.py`](../eplus_gym_app/ecm_panel.py).

## A04 / VAV honesty

Practice champion (Lakeside A04) is **ZoneHVAC:WaterToAirHeatPump** with
**0 air loops**. Guideline 36 / VAV AHU measures that patch air-loop SAT/DSP
are **N/A or CONCEPTUAL** until a VAV twin is published. WAHP-relevant
spreadsheet ECMs (schedule align, setback, applicable plant lockouts) may still
publish.

**GL36 FDD** cookbook rules (open-fdd FC1–FC15) are fault detection — not this
tab. Energy ECMs use `open_fdd.ecm_engineering` calculators / packages.

## Contract

See [`DATA_CONTRACT.md`](DATA_CONTRACT.md) § ecm_compare.json. Never invent
`ss_*` savings numbers.
