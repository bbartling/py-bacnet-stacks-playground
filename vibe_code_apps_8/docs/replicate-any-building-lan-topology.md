# Recreating BAS Lite (App 8) on any HVAC OT LAN

This note is for operators and integrators who need the same App 8 **modular VOLTTRON** edge stack on a different site, VLAN, or BACnet plant layout. Nothing here assumes a particular bench hostname or IP range.

## 1. What must stay aligned

| Layer | What to configure |
|--------|-------------------|
| **Network** | Edge host can reach field controllers on the BACnet / OT VLAN (routing, ACLs, BBMD if used). |
| **BACnet** | `BACpypes.ini` (or stack equivalent), UDP 47808 bind interface, BBMD table if applicable. |
| **Platform Driver** | One registry CSV (or driver-specific config) per device identity; device names must match what the agent subscribes to. |
| **App 8 web agent config** | `bacnet_devices`, `route_prefix`, alarms, `site_name`, optional schedule/driver store paths. |
| **Reverse proxy** | Caddy (or other) upstream URL, Basic Auth secrets, TLS policy. See `vibe_code_apps_8/caddy/README.md`. |

## 2. Platform Driver device identities

The runtime subscribes to driver publishes (`devices/<id>/all`) and writes via `platform.driver` RPC.

- Use **stable string identities** that match your driver config (often the same as the CSV/registry folder name under `devices/`).
- Prefer a naming convention that scales: `campus/building/ahu_01` or `SITE_AHU01` — avoid embedding IP addresses in the identity unless that is already your standard.

## 3. Site model (no Python edits for a new building)

Define device identities in Platform Driver first, then align App 8 point metadata and alarms in `app8_web_agent/agent.py` or future site-model config.

## 4. OAT share and other small agents

Any agent that references device or point names must use the **same identities** as Platform Driver. After renaming devices, update `oat_share_agent` config (or equivalent) so source and target device ids and point names match the live plant.

## 5. Deploy from a Windows workstation

Build + run from this folder:

```powershell
.\rebuild-bas-lite.ps1 -RebuildFrontend
```

## 6. Checklist before go-live

1. From the edge shell: `docker compose ps` and `docker compose logs --tail=100 volttron caddy`.
2. `curl -sS http://127.0.0.1:8080/app8/api/health` — `counts.devices` / `points` non-zero when live topics flow.
3. BACnet **who-is / read** from the same interface the driver uses (firewall and binding).
4. For BACnet broadcast issues on Linux, use `docker-compose.hostnet.yml` fallback profile.

## 7. Non-BACnet drivers

The UI is **driver-agnostic**: anything published through VOLTTRON and mapped by point metadata can render in the same pages. BACnet is the reference implementation in this repo; Modbus, SNMP, or custom drivers follow the same pattern as long as identities and point names match.
