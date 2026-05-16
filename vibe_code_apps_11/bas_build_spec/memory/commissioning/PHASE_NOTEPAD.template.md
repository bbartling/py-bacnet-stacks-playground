# Commissioning phase notepad — template (new job)

Copy to **`PHASE_NOTEPAD.md`** and replace every `(fill)`. **This file is the only place** for site-specific bind, NIC, device instances, and URLs.

---

## A) BACnet bind & LAN topology

| Field | Your value |
|-------|------------|
| **BACnet bind string** (IP/prefix[:udp]) | `(fill)` e.g. `10.20.30.50/24:47808` |
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
| **HVAC archetype** | `(fill)` e.g. VAV+AHU, VRF+DOAS, lab AHU, hospital isolation |
| **Construction stage** | `(fill)` |

---

## C) BACnet devices (expected on wire)

- `(device-instance)` — `(role)`, IP/MS-TP, notes

---

## D) Dial-in & firewall (no secrets)

| Field | Your value |
|-------|------------|
| **UI URL** | `http://<head-end-ip>:5173/` |
| **API base** | `http://<head-end-ip>:8000/` |
| **Ports** | `5173/tcp`, `8000/tcp`, `47808/udp` |
| **BAS_ALLOWED_ORIGINS** | `(fill)` |

---

## E) Phase status strip

**Active phase:** `(fill)`  
**Done so far:** `(fill)`  
**Next:** `(fill)`  
**Dashboard URL:** `(fill)`

---

## F) Chronological log

- `YYYY-MM-DD (phase) — (fill)`
