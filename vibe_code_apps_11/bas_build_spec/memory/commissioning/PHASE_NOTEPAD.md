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
| **BACnet bind string** (IP/prefix[:udp]) | `(fill)` e.g. `192.168.204.18/24:47808` |
| **NIC name** (Linux `ip` / `en*`) | `(fill)` |
| **Head-end IPv4** | `(fill)` |
| **Subnet / CIDR** | `(fill)` |
| **Default gateway** | `(fill)` |
| **VLAN / path notes** | `(fill)` |

---

## B) Building & HVAC

| Field | Your value |
|-------|------------|
| **Site / job label** | `(fill)` |
| **HVAC archetype** | `(fill)` |
| **Construction stage** | `(fill)` |

---

## C) BACnet devices (expected on wire)

*(Bullet list — device instance, brief role, MS/TP vs IP.)*

- `(fill)`

---

## D) Dial-in & firewall (no secrets)

| Field | Your value |
|-------|------------|
| **UI URL** | `(fill)` e.g. `http://192.168.204.18:5173/` |
| **API base** | `(fill)` e.g. `http://192.168.204.18:8000/` |
| **Ports opened on head-end** (site checklist) | `(fill)` e.g. `5173/tcp`, `8000/tcp`, `47808/udp` |
| **`BAS_ALLOWED_ORIGINS`** UI origin(s) | `(fill)` |

---

## E) Phase status strip (human + agent keep current)

**Active phase:** `(1 electrician | 2 Cx+P2P | 3 TAB | 4 final BAS)` — `(fill)`

**Done so far (short):**  
- `(agent/human bullets — what shipped or was verified on site)`

**Next phase intent (one line):**  
- `(fill)`

**Dashboard / mode URL (when implemented):**  
- `(fill)` e.g. `http://<ip>:5173/#/electrician` or `?mode=electrician` — update when `bas_app` defines the route.

---

## F) Chronological log (append — newest at bottom)

- **Template:** `YYYY-MM-DD (phase) — <what changed / verified>; URLs: <if changed>`

---

*(No log lines yet.)*
