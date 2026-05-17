# Rough-in commissioning context (wake export)

Generated (UTC): 2026-05-17T18:06:36.204813Z
Cutoff (last bas_wake `last_run_at`): 2026-05-17T16:11:02.944443Z
Chat source: `/home/ben/bas_app/runtime/rough_in_chat.json`
Messages since cutoff: 4 (user: 2, assistant: 2)

Codex (**mini and gpt-5.5 critique**): read this entire file every wake.
Do not rely on `rough_in_chat_summary.md` (latest turn only).

## Pinned site context (from PHASE_NOTEPAD.md)

_Always read — survives across wakes even when chat slice is empty._

## A) BACnet bind & LAN topology

| Field | Your value |
|-------|------------|
| **BACnet bind string** (IP/prefix[:udp]) | `192.168.204.18/24:47808` |
| **NIC name** (Linux `ip` / `en*`) | `enp3s0` |
| **Head-end IPv4** | `192.168.204.18` |
| **Subnet / CIDR** | `/24` |
| **Default gateway** | `(fill)` |
| **VLAN / path notes** | `Operator-provided candidate bind; unverified.` |

---

## B) Building & HVAC

| Field | Your value |
|-------|------------|
| **Site / job label** | `VRF + DOAS rough-in` |
| **HVAC archetype** | `VRF + DOAS with expected VAV boxes` |
| **Construction stage** | `Rough-in / Phase 1` |

---

## C) BACnet devices (expected on wire)

*(Bullet list — device instance, brief role, MS/TP vs IP.)*

- `3456788` - Waterproof 1-Wire DS18B20 / Pi temperature sensor, BACnet-presenting Pi device discovered on wire.
- `3456790` - VAV, IP, operator-provided expected device.
- `3456789` - AHU, IP, operator-provided expected device.

---

## D) Dial-in & firewall (no secrets)

| Field | Your value |
|-------|------------|
| **UI URL** | `http://192.168.204.18:5173/` |
| **API base** | `http://192.168.204.18:8000/` |
| **Ports opened on head-end** (site checklist) | `5173/tcp`, `8000/tcp`, `47808/udp` |
| **`BAS_ALLOWED_ORIGINS`** UI origin(s) | `(fill)` |

---

## E) Phase status strip (human + agent keep current)

**Active phase:** `(1 electrician | 2 Cx+P2P | 3 TAB | 4 final BAS)` — `(fill)`

**Done so far (short):**  
- Operator pasted rough-in context: VRF + DOAS job, VAV `192.168.204.14` / device `3456790`, AHU BACnet device `3456789`, and candidate head-end bind `192.168.204.18/24:47808` on `enp3s0`.
- **Human correction (2026-05-16):** AHU IPv4 is **`192.168.204.13`** (rough-in chat once showed `.113` — treat as typo; use `.13` in tables and discovery).
- Real BACnet polling / Who-Is requested in chat; **still gated** until lab sign-off in `BUILD_CHECKPOINTS.md`.

**Next phase intent (one line):**  
- Human lab sign-off for BACnet polling and bind confirmation.

**Dashboard / mode URL (when implemented):**  
- `(fill)` e.g. `http://<ip>:5173/#/electrician` or `?mode=electrician` — update when `bas_app` defines the route.

---

---

## Chat since last bas_wake

## 1. user @ 2026-05-17T18:01:26.255513Z

VRF + DOAS with expected VAV boxes.

## 2. assistant @ 2026-05-17T18:01:26.328163Z

**Next cron runs:** Codex build: 3:00 PM CDT · BACnet Who-Is: due now · BACnet auto-arm: due now · BACnet point scrape ever: due now. Note saved. **Codex** (critique + minis) replies on the next builder wake; live values are on the **device tree**.

## 3. user @ 2026-05-17T18:05:35.738103Z

VRF + DOAS with expected VAV boxes.

## 4. assistant @ 2026-05-17T18:05:35.827349Z

**Next cron runs:** Codex build: 3:00 PM CDT · BACnet Who-Is: 1:10 PM CDT · BACnet auto-arm: 1:10 PM CDT · BACnet point scrape ever: 1:10 PM CDT. Note saved. **Codex** (critique + minis) replies on the next builder wake; live values are on the **device tree**.
