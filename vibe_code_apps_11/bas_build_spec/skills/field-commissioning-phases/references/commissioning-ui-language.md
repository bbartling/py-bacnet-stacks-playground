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

## Electrical phase MVP (rough-in `/rough-in/`)

**Show (primary):**

1. **BACnet adapter / bind** — one card: bind `IP/prefix:47808`, NIC name, last Who-Is UTC, I-Am count, next cron runs.
2. **Device + point tree** — bind → device (`#instance`, IPv4, **Online** or **On wire (not in job list)**) → child rows: `analog-value,1 present-value = 72.3` from latest 5-min scrape.
3. **Chat** — short status + next Codex / Who-Is schedule.

**Hide or collapse for this phase:** separate driver table + networking table + flat device table + full point-scrape debug grid (engineers can use JSON logs).

**Status labels (operator):**

| Internal | Show electrician |
|----------|------------------|
| `online` | **Online** |
| `discovered_not_staged` | **On wire (not in job list)** |
| `no_iam` | **No I-Am / Stale** |
| `pending` / `gated` | **Pending Who-Is** |

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

- **Workers** (Who-Is, point scrape) do **not** post to chat — data lives on the **device tree** only (`BAS_ROUGH_IN_WORKER_CHAT=false` default).
- **Instant reply** after an operator note: **next cron runs** only + “note saved for next Codex wake.”
- **Codex** posts one message after each `bas_wake`: **gpt-5.5 critique** + mini count (`bas_post_wake_rough_in_chat.sh`).
- Do not dump discovery log blocks or object-list errors into chat.
