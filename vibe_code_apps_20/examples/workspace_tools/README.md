# Workspace tools (seed for `/data/tools`)

Copy or symlink these campaign scripts into the shared Studio volume:

```text
$WATTLAB_HOST_WORKSPACE/tools/   ↔   /data/tools
```

Prefer product CLIs when they exist (`wattlab geo-idf`, `dial-loads`,
`score-monthly`, `controls-checklist`). Keep this folder for ladders and
site experiments.

**Primary AI handoff:** `vibe20_agent_spec/docs/AGENT_CONTEXT.md`  
**Dial depth + script index:** `vibe20_agent_spec/docs/TWIN_DIAL_PLAYBOOK.md`,
`vibe20_agent_spec/docs/AGENT_TOOLS.md` (skill `wattlab-twin-calibrate-dial`).

## Controls checklist

Product path (tip image):

```bash
docker exec vibe20 wattlab controls-checklist \
  --dump /data/uploads/dump/wattlab_dump_BUILDING.zip \
  --out-dir /data/reports/controls_checklist \
  --docx
```

Optional thin wrapper (`controls_service_checklist.py` in this folder):

```python
from wattlab.existing_building.controls_checklist import main
raise SystemExit(main())
```

Prefer product CLIs over fat copies of `build_geo_idf` / `dial_loads_mcp` /
`score_b100_monthly` when the tip image has them.

## Seeded scripts (this folder)

| Theme | Files |
| --- | --- |
| Controls | `controls_service_checklist.py` (thin), `analyze_hws_reset.py` |
| Geometry | `build_stacked_6floor_idf.py`, `build_geo_idf.py` (prefer `wattlab geo-idf`) |
| Loads / envelope | `patch_reheat_envelope.py`, `apply_doe_vintage_5a.py`, `dial_loads_mcp.py` |
| Score / ladders | `score_g14_monthly.py`, `write_calibration_scorecard.py`, `save_best_model.py`, `score_b100_monthly.py`, `run_gas_g14_ladder.py`, `run_vintage_ladder.py`, `compare_open_meteo_bills.py` |

Pass paths for **any** building — do not hardcode campus names into new scripts.
