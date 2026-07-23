---
name: wattlab-controls-fdd
description: >-
  Use when building a controls-tech handoff from vibe19 WattLab dumps: VAV
  comfort, damper/flow FDD, sensor health, PID hunting, fan-off static smells,
  soft ECM flags, or DOCX checklists. Also when fault counts look epidemic /
  false-positive heavy and the agent should retune vibe19 FDD. Triggers on:
  controls checklist, FDD dump, VAV-4, VAV-5, false positive, FP tuning,
  controls-checklist, openfdd, rcx comfort.
---

# WattLab — controls FDD checklist + vibe19 FP tuning

Pure dump consumer. No EnergyPlus. Prefer product CLI over `/data/tools` copies.

## Files

| Path | Role |
| --- | --- |
| `wattlab/existing_building/controls_checklist.py` | Analyze dump → MD/JSON/DOCX |
| `docs/AGENT_TOOLS.md` | `/data/tools` vs WattLab CLIs |
| `examples/workspace_tools/` | Seed scripts for host `tools/` |

## Quick use

```bash
wattlab controls-checklist \
  --dump /data/uploads/dump/wattlab_dump_BUILDING.zip \
  --out-dir /data/reports/controls_checklist \
  --docx \
  --fp-tuning-note "Retuned VAV-5 gate after epidemic; before 42 FAULTs → after 6"
```

Repeat `--dump` for campus. DOCX needs `python-docx` (`pip install 'wattlab[docx]'` or studio extra).

## Unusual / false-positive loop (required agent behavior)

1. Run checklist once on the fresh vibe19 dump.
2. If JSON/MD shows `agent_should_iterate_vibe19: true` (epidemic VAV rules,
   many high_suspect / near-100% rows), **do not** treat the punch list as final.
3. In **vibe19**: open FDD Plots + RCx; fix role map / proofs; tighten gates or
   thresholds that are clearly false-positive heavy; re-export dump.
4. Re-run `wattlab controls-checklist` on the new dump.
5. Pass `--fp-tuning-notes` (file) and/or `--fp-tuning-note` (inline) summarizing:
   - what looked excessive (rule_id, counts)
   - what changed in vibe19
   - before → after fault counts
6. Those notes land in the **Agent FDD false-positive tuning** section of MD and DOCX.

Heuristics (in code): `fault_pct ≥ 95%`, near-window continuous hours, same VAV
rule FAULT on ≥40% of boxes, schedule near-always FAULT, telemetry conflicts
(e.g. VAV-5 while damper median not closed).

## Hard rules

1. Checklist ≠ calibrated energy / ROI report.
2. Soft ECM flags are investigation themes only.
3. Epidemic / high_suspect → iterate vibe19 before dispatching techs.
4. Always note FP-tuning attempts in the report when you retuned.
5. Prefer `wattlab controls-checklist` over ad-hoc copies under `/data/tools`
   once the tip image includes it; tools bin is fine for campaign-only scripts.
