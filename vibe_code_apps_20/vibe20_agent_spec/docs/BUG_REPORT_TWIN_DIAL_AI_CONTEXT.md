# BUG_REPORT — Twin dial AI context gaps + generic G14 dial recipe

**Purpose:** This is **not** a Liberty building log. It is (1) where agent/report/skill
context falls short for dialing EnergyPlus twins to utility bills, and (2) a
**generic** recipe distilled from a dual-AHU campaign that reached full G14.

**Status:** Method SoT until playbook + skills fully absorb §2. Campus run tables
stay in `BEST_MODELS` / liberty reports only — do not paste building IDs here as
product defaults.

G14 gate (both fuels): **|NMBE| ≤ 5%** and **CVRMSE ≤ 15%**.

Example outcome (shape-led campaign, fuel-agnostic lesson):

| Fuel | NMBE | CVRMSE | Pass |
|------|------|--------|------|
| Elec | −2.6% | 14.8% | yes |
| Gas | −0.2% | 15.0% | yes (barely) |

---

## 1. Where AI context is falling short

### A. Reports (`wattlab_workspace/reports/`)

| Gap | Why it hurts agents |
|-----|---------------------|
| **No durable “ops / as-operated” dial chapter** | Agents only see envelope→SAT→VAV playbooks. They miss: fan runtime by month, 24/7 + 0% OA months, partial HW (daytime) vs plant kill. |
| **BUG_REPORT used as campus scratch** | Builder agents get building IDs / run names instead of transferable dial physics. |
| **No tradeoff matrix (elec↔gas)** | Cool DAT + long fans fixes elec short → reheat gas explodes. Full HW off fixes gas spike → gas −100% that month. **Partial HW hours** is the missing middle — undocumented in reports. |
| **No “which fuel first?” decision tree** | Skills say “gas before elec.” Campaign needed **elec-first** when spring chiller / Oct cooling dominated CV, then gas recovery. Reports don’t say when to flip order. |
| **Scoreboard ≠ method** | `BEST_MODELS` / liberty tables list pass/fail runs but not the *generic knob sequence* that closed CV. |
| **Provisional near-gate CV** | Barely-≤15% gas CV has no “freeze vs keep dialing” rule in reports. |

### B. Tools docs (`wattlab_workspace/tools/`)

| Artifact | Has | Missing |
|----------|-----|---------|
| `TWIN_DIAL_PLAYBOOK.md` | Envelope, banded SAT, VAV min, OA, CHW free-cool, soft HW | Operator fan/OA schedules; HW **availability by hour**; elec-first path; reheat coupling trap |
| `AGENT_CONTEXT.md` | Best-run pointers, ECM after G14 | Points at BUG_REPORT for bugs — but no dial physics; still campus-run-centric |
| `skills/wattlab-twin-calibrate-dial` | Phase 0–3, Liberty-heavy triggers | Same gaps as playbook; description still Building 50/100–centric |
| `patch_dual_ahu_from_dump.py` | Dump DAT/fan, soft HW, `--oct-plant-off` | No flags for: Aug 24/7+0% OA, Mar–Jun short fans, Aug/Oct **daytime HW**, winter fan cut |
| `dial_dual_ahu_ops_*.py` | **Encoded the winning knobs** (scripts) | Not lifted into playbook/skill/report — tribal knowledge in one-off CLIs |
| `score_g14_monthly.py` | Correct gate | No “monthly residual → suggested knob” helper for agents |

### C. vibe20 agent spec (`py-bacnet-stacks-playground/.../vibe20_agent_spec`)

| Has | Missing |
|-----|---------|
| Twin dial skill + playbook + Studio/ECM skills | No skill for **as-operated schedule hypothesis** from FDD/dump → IDF |
| Controls-FDD skill | Does not close the loop: FDD finding → monthly bill residual → G14 knob |
| Docs assume gas-then-elec | No dual-fuel CV chess (hold elec pass while dialing gas) |

### D. open-fdd (`open-fdd/openfdd_agent_spec`)

| Has | Missing |
|-----|---------|
| Architecture: “E+ calibration stays in vibe20” | **Zero** G14 / NMBE / CVRMSE / dial skills |
| SQL FDD, cookbook, ECM engineering | No “fault / ops story → Twin schedule patch” skill |
| Ownership splits FDD vs Twin | Agents in open-fdd have no recipe when bills disagree with model |

### E. Eval

| Gap |
|-----|
| No eval harness that scores an agent on: given monthly ±% table → propose ≤N knobs → expect CV improvement without flipping the other fuel |
| No golden “tradeoff traps” cases (cool Oct DAT; HW full-off; May CHW off) |

**Bottom line:** Tools *implement* pieces of the dial; skills/playbooks teach envelope+SAT era; **reports never captured the ops/reheat chess that actually closed dual-fuel G14.** Planet-wide, there is still no first-class agent skill for that loop.

---

## 2. Generic dial recipe (transferable — no campus IDs)

### Gate
Both fuels: `|NMBE| ≤ 5%` and `CVRMSE ≤ 15%`. Annual % alone ≠ calibrated.

### Order (adaptive)
1. **Geometry + AMY + bills lock**
2. **Annual** short/long → envelope / LPD (classic)
3. Look at **which fuel’s CV fails** and **which months**:
   - Elec long in spring / short in peak cool months → **runtime & OA & DAT** (ops) before more glass
   - Gas CV fail with elec already pass → **reheat / HW / winter fans** only (do not undo elec knobs blindly)
4. One hypothesis per run; score both fuels every time

### Elec-shape knobs (as-operated)
| Symptom | Try |
|---------|-----|
| Shoulder months elec **long** | Shorten AHU fan hours those months |
| Peak cool month elec **short** | Longer fans and/or cooler DAT and/or lower OA (more mechanical) |
| Peak month short + dump says recirc | **Fans on, OA ≈ 0** (even 24/7) |

### Gas recovery without killing elec (the missing chapter)
| Symptom | Try | Trap |
|---------|-----|------|
| Gas spike after cooler DAT / longer fans | **Daytime-only HW** in spike months (not full plant off) | Full HW off → that month gas → −100% vs bills |
| Still high gas in dump month | Soften HW OA-reset high SP; warm DAT slightly; shorten HW hours | Cooler DAT alone without HW control |
| Winter gas high | Shorter winter fan hours; softer HW | Cutting OA/fans can also cut useful reheat shoulder months |
| Shoulder gas short | Cooler DAT and/or higher VAV min-flow those months | Raises chiller elec — watch elec CV |
| Near gas CV gate (~15–17) | Stack small knobs: winter fans + spring DAT + VAV min bump | One big plant-off usually overshoots |

### Reheat coupling (always print this)
```
more mechanical cooling (cool DAT, long fans, low OA)
  → more reheat opportunity
  → gas up unless HW is scheduled/softened
```
Dial **both sides** of the coil story.

### Score honesty
- Prefer dual pass with gas CV **barely** ≤15 only as provisional; freeze after a margin or document “edge pass.”
- Never promote a run that flips the previously-passing fuel.

---

## 3. What to add next (implementation backlog — not this docs pass)

1. Lift ops CLI patterns into `patch_*` flags + playbook section (partially absorbed in playbook §2c / skill).
2. vibe20 eval: 3 golden monthly residual → knob quizzes (cool-DAT reheat trap; HW full-off trap; elec-first then gas).
3. Keep this BUG_REPORT as the **method** SoT until playbook/skill absorb it fully; campus run tables stay in `BEST_MODELS` / liberty only.
