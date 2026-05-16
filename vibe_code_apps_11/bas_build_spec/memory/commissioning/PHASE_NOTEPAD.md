# Commissioning phase notepad (human + Codex)

**Single living handoff** for LAN topology, BACnet, building context, dial-in URLs, and phase status. **No secrets** (no passwords, no private keys). Prefer **instance numbers / device types**, not customer PII.

---

## Step 1 — Paste your site context (human fills first)

**Copy/paste prompt for humans (Codex / in-app notepad should mirror this text on first open):**

> **Paste your info into me** — I need this before BACnet and dashboards make sense:
>
> 1. **BACnet LAN / bind** you will use (see `bas_build_spec/bacnet_scripts.md`): e.g. `--address 192.168.x.x/24:47808` on the **NIC that reaches the MS/TP router or BACnet/IP devices** (not `docker0` / not `lo` unless intentional).
> 2. **LAN topology** in one screen: head-end IP, subnet mask or prefix, gateway, VLAN IDs if relevant, BBMD / NAT notes if any.
> 3. **Building / job**: name or code, HVAC archetype (e.g. VAV+AHU, VRF+DOAS), floor/stage of construction.
> 4. **BACnet devices** you expect on the wire: device IDs, object types you care about first, MS/TP vs IP, known **offline** devices for later alarm tests.
> 5. **Dial-in URLs** you use: UI `http://<head-end-ip>:5173/`, API `http://<head-end-ip>:8000/`, and any `?api=` override.

Fill the **structured blocks** below (replace `(fill)`).

---

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

- `3456788` - Waterproof 1-Wire DS18B20 / Pi temperature sensor, discovered on wire, not a BACnet device.
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

## F) Chronological log (append — newest at bottom)

- **Template:** `YYYY-MM-DD (phase) — <what changed / verified>; URLs: <if changed>`
- `2026-05-16 (phase 1) — Captured operator-provided rough-in context in the notepad: VAV+AHU, VAV 192.168.204.14 / device 3456790, AHU 192.168.204.113 / device 3456789, candidate BACnet bind 192.168.204.18/24:47808 on enp3s0; real polling remains gated.`
- `2026-05-16 (phase 1) — Human correction: AHU IP is 192.168.204.13 (not .113). Who-Is on bind 192.168.204.18/24:47808 only after explicit lab sign-off in BUILD_CHECKPOINTS.`
- `2026-05-16 (phase 1) — Operator updated the archetype to VRF + DOAS with expected VAV boxes and identified 3456788 as a Waterproof 1-Wire DS18B20 / Pi temperature sensor discovered on 192.168.204.12; keep the staged VAV/AHU bind facts intact.`
- `2026-05-16 (phase 1) — Synced the durable rough-in record to the VRF + DOAS job, retained the staged VAV 3456790 and AHU 3456789 facts, and kept 3456788 visible as a non-BACnet temperature sensor in the public device tree.`

---

*(No log lines yet.)*
