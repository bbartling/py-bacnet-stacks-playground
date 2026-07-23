# Agent tools bin (`/data/tools`)

Shared host folder for **campaign scripts** that are not (yet) product CLIs.
Mounted as `$WATTLAB_HOST_WORKSPACE/tools` ↔ `/data/tools` inside vibe19/vibe20.

Prefer packaged WattLab commands when they cover the job:

| Need | Prefer |
| --- | --- |
| Site-scale massing | `wattlab geo-idf` |
| Lights / equip / infil dial | `wattlab dial-loads` |
| Monthly vs bills score | `wattlab score-monthly` |
| Controls FDD checklist + DOCX | `wattlab controls-checklist` |
| Bills → EUI peer bands | `wattlab benchmark` |

Use `/data/tools/<script>.py` for vintage ladders, gas G14 campaigns, stacked
floor IDFs, HWS peeks, or one-off site experiments. Seed copies live in
[`examples/workspace_tools/`](../../examples/workspace_tools/).

## Layout

```text
$WATTLAB_HOST_WORKSPACE/
  tools/                 # campaign scripts (this bin)
  uploads/dump/          # vibe19 wattlab_dump_*.zip
  reports/controls_checklist/
  .artifacts/<campaign>/
```

## Controls checklist + false-positive tuning

```bash
docker exec vibe20 wattlab controls-checklist \
  --dump /data/uploads/dump/wattlab_dump_BUILDING.zip \
  --out-dir /data/reports/controls_checklist \
  --docx \
  --fp-tuning-notes /data/reports/controls_checklist/fp_tuning_log.md
```

If unusual/suspect fault counts look epidemic, agents **must** iterate vibe19
FDD (thresholds / gates / role map), re-export, and record before/after notes
in the MD/DOCX **Agent FDD false-positive tuning** section. Skill:
`skills/wattlab-controls-fdd/SKILL.md`.

## Run a campaign script

```bash
docker exec -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace \
  -e ENERGYPLUS_DOCKER_USER=1000:1000 -e PYTHONUNBUFFERED=1 vibe20 \
  python /data/tools/<script>.py --help
```

Do **not** hardcode client site names into new scripts — pass paths/args.

See also: [`AGENT_DOCKER_WORKSPACE.md`](AGENT_DOCKER_WORKSPACE.md),
[`ESCO_RETROFIT_COST_ROI.md`](ESCO_RETROFIT_COST_ROI.md).
