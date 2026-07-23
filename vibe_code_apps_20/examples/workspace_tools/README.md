# Workspace tools (seed for `/data/tools`)

Copy or symlink useful campaign scripts into the shared Studio volume:

```text
$WATTLAB_HOST_WORKSPACE/tools/   ↔   /data/tools
```

Prefer product CLIs when they exist (`wattlab geo-idf`, `dial-loads`,
`score-monthly`, `controls-checklist`). Keep this folder for ladders and
site experiments.

## Controls checklist

Product path (tip image):

```bash
docker exec vibe20 wattlab controls-checklist \
  --dump /data/uploads/dump/wattlab_dump_BUILDING.zip \
  --out-dir /data/reports/controls_checklist \
  --docx
```

Optional thin wrapper (if you still keep a script in the bin):

```bash
# /data/tools/controls_service_checklist.py — thin re-export
from wattlab.existing_building.controls_checklist import main
raise SystemExit(main())
```

When FDD positives look excessively high, iterate vibe19 FDD tuning and pass
`--fp-tuning-notes` / `--fp-tuning-note` so DOCX reports include the log.
See `vibe20_agent_spec/docs/AGENT_TOOLS.md` and skill `wattlab-controls-fdd`.

## Script themes (bring your own copies)

| Theme | Examples |
| --- | --- |
| Controls | dump HWS peek, checklist wrapper |
| Geometry | stacked-floor IDF builders |
| Loads / envelope | vintage climate patches, reheat/SAT patches |
| Score / ladders | gas G14 ladder, vintage ladder, Open-Meteo vs bills |

Pass paths for **any** building — do not hardcode campus names into new scripts.
