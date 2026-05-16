# Commissioning UI language (operator-facing)

Internal code may use `simulator`, `simulator_only`, or mock drivers for the **demo supervisor** at `/`. **Public commissioning surfaces** (`/rough-in/` and future phase shells) must **not** lead with simulator branding — electricians read this as “fake data.”

## BACnet / driver status table (rough-in)

**Do not show:** “Simulator-only path”, “Simulator mock”, `simulator_only` as the primary label, or “Real BACnet discovery disabled by default” as the headline.

**Show instead (field labels):**

| Field | Example value | Notes |
|-------|----------------|-------|
| Driver mode | **Wire off — lab gate** | Until human sign-off in `BUILD_CHECKPOINTS.md` § BACnet lab sign-off |
| Driver mode | **Discovering** / **Polling** | After sign-off + Who-Is / read cycle started |
| Bind (planned) | from **PHASE_NOTEPAD § A** | BACpypes3 `--address`; site NIC name |
| Last wire activity | timestamp or **Not started** | Who-Is / I-Am log time when applicable |
| Access | Read only | Public rough-in |
| CORS | Same-host LAN default | When `BAS_ALLOWED_ORIGINS` unset |

## Devices / points table

- Before sign-off: **Staged (operator)** — rows from chat / `PHASE_NOTEPAD.md`, status **Pending Who-Is**.
- After Who-Is: **Discovered** / **No I-Am** / **Online** from wire evidence.
- Never label operator-staged rows as “simulator” devices.

## Internal vs display

- API may keep `bacnet_driver_status.state=simulator_only` internally until wire is on; **map** to operator strings in JSON (`driver_mode_label`, `wire_state`) for the public snapshot.
- Demo operator shell (`/`) may still use simulator-backed points; that is separate from rough-in.

## Who-Is

- **Only after** human checks **§ BACnet lab sign-off** in `BUILD_CHECKPOINTS.md`.
- First wire step: **Who-Is** on validated bind; log to `memory/integrations/bacnet.md`.
- Scheduled Codex wakes must not Who-Is without that sign-off.

## Commissioning chat replies

Rough-in chat uses a **local rules engine** (not an LLM). Each assistant turn should append **next automation run** from `bas_wake_status.sh` / `jobs.json` schedule (local time, e.g. `Next automation run: 10:00 AM CDT.`) and mention **waiting_human** when `cron_codex/state/waiting_human` exists.
