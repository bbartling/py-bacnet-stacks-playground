# Agent context — WattLab Studio twin calibrate / dial

**Audience:** Cursor / product agents building WattLab Studio features that touch
EnergyPlus twins, Uploads, G14 scoring, or dial UX.

**Use:** Drop this file into agent context first. High-level only — not a run log.

**Not for:** Paste entire `reports/CALIBRATE_SESSION.md` or `.artifacts/` ladders
into every chat unless debugging a specific campaign.

---

## Product truth (one paragraph)

WattLab Studio twins are EnergyPlus models scored against **monthly utility
bills**. ASHRAE Guideline 14–style gates: **|NMBE| ≤ 5%** and **CVRMSE ≤ 15%**
on **both** electricity and natural gas. Stacked campus twins (HVACTemplate →
ExpandObjects) keep plant/terminal flows **`autosize`**. Calibration is
**envelope → internal gains → as-operated controls / schedules**, not “pick
boiler tons.” Product CLIs: `wattlab geo-idf`, `wattlab dial-loads`,
`wattlab score-monthly`. Workspace CLIs live under `/data/tools` (host:
`~/wattlab_workspace/tools`).

---

## Dial order (do not skip)

1. **Geometry** — Confirm what the human wants (e.g. N stacked floors × 1 zone).
   DOE midrise×4 perimeter-core is a different twin; do not substitute silently.
2. **Weather + bills** — AMY EPW overlapping bill months. Bills must match the
   building (shared elec allocation + **that** building’s gas).
3. **Annual gas short → envelope first** — Raise WWR, then leakier glass U, then
   infiltration ACH. Do **not** start with plant oversizing.
4. **Annual elec short → EPD / LPD** — Hold these steady while chasing gas
   **shape** once annual elec is near gate.
5. **Monthly gas CVRMSE** — After annual gas ~flat. Use **vibe19 AHU DAT** (or
   site ops) before inventing SAT. Typical levers: seasonal/banded cooling SAT,
   scheduled VAV min-flow, **seasonal outdoor-air hours** (often more powerful
   than SAT alone when bills ≠ HDD).
6. **Monthly elec CVRMSE** — After gas is near/pass. Prefer **month-aware light /
   equipment schedules** over blunt annual LPD cuts (flat cuts trade months and
   can break gas).
7. **Publish** — Score both fuels → write Twin G14 scorecard → promote CURRENT /
   best model when the human asks.

---

## Hard-won rules (agents keep relearning these)

| Rule | Why |
| --- | --- |
| Annual flat ≠ monthly good | Winter/summer can cancel; CVRMSE still fails. |
| Bills ≠ HDD | Peak bill months may not match coldest weather — fix with OA/ops, not more glass. |
| Cold summer SAT only where DAT dumps | Broad “Apr–Oct @ 50°F” can blow shoulder months (Oct/Aug). |
| Gas shape before elec shape | Elec-first LPD cuts often wreck a hard-won gas pass. |
| Autosize stays on | Dialing ≠ naming plant capacity. |
| Paths/args for any building | Never bake one campus id into product defaults. |
| G14 needs **both** fuels | Gas-only pass is not done. |

---

## What “done” looks like

- Scorecard + monthly charts for both fuels (including monthly ±% dial chart).
- Preferred IDF / run promoted (Uploads + `CURRENT_RUN` / best-model freeze).
- Assumptions logged (envelope + controls + schedule story in one place).

---

## Where to go deeper (optional)

| Doc | When |
| --- | --- |
| [`TWIN_DIAL_PLAYBOOK.md`](TWIN_DIAL_PLAYBOOK.md) | Ordered phases + practice trajectory |
| Skill `wattlab-twin-calibrate-dial` | Agent skill frontmatter + same phases |
| [`AGENT_TOOLS.md`](AGENT_TOOLS.md) | `/data/tools` campaign scripts vs product CLIs |
| Product `wattlab-assumptions` | Short/long fuel + checklist |
| `reports/CALIBRATE_SESSION.md` | One campus’s full dial log (not default context) |

---

## Studio wiring (agents shipping features)

- Twin G14 UI reads **scorecard JSON**, not raw `eplusout.sql` alone.
- Uploads / prototypes path must match where dialed IDFs are published.
- Engineering Findings (docx/json) is a **separate** reporting path from twin
  calibrate — do not conflate FDD findings DOCX with G14 dial status.
- ECMs tab: checkbox proxies vs calibrated Twin baseline; ERV / toilet-exhaust
  recovery are **PRODUCTION_PROXY_ONLY** until an EnergyPlus patch lands.
