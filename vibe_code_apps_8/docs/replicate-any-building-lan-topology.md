# Recreating BAS Lite (App 8) on any HVAC OT LAN

This note is for operators and integrators who need the same **VOLTTRON + Platform Driver** edge stack on a different site, VLAN, or BACnet plant layout. Nothing here assumes a particular bench hostname or IP range.

## 1. What must stay aligned

| Layer | What to configure |
|--------|-------------------|
| **Network** | Edge host can reach field controllers on the BACnet / OT VLAN (routing, ACLs, BBMD if used). |
| **BACnet** | `BACpypes.ini` (or stack equivalent), UDP 47808 bind interface, BBMD table if applicable. |
| **Platform Driver** | One registry CSV (or driver-specific config) per device identity; device names must match what the agent subscribes to. |
| **App 8 agent** | `bacnet_devices`, optional `site_model_path` / inline `devices` + `points`, alarms, `site_name`, `volttron_root`, `vctl_path`. |
| **Reverse proxy** | Caddy (or other) upstream URL, Basic Auth secrets, TLS policy. See `vibe_code_apps_8/caddy/README.md`. |

## 2. Platform Driver device identities

The web agent subscribes to `devices/<device_id>/all` for each id in **`bacnet_devices`** in `app8_web_agent/config`.

- Use **stable string identities** that match your driver config (often the same as the CSV/registry folder name under `devices/`).
- Prefer a naming convention that scales: `campus/building/ahu_01` or `SITE_AHU01` — avoid embedding IP addresses in the identity unless that is already your standard.

## 3. Site model (no Python edits for a new building)

You can describe equipment and points in JSON instead of editing `agent.py`.

**Option A — external file** (next to the agent package or absolute path):

```json
{
  "site_model_path": "site_model.json"
}
```

**Option B — inline** in `config` (same schema as the file): top-level keys `devices`, `points`, optional `alarm_definitions`.

Schema summary:

- **`devices`**: object keyed by device id; each value may include `displayName`, `kind`, `address`, BACnet `deviceId`, `pollingEnabled`, etc. Point live values still arrive via VOLTTRON publish; `points` starts as `{}`.
- **`points`**: array of objects with `pointId`, `deviceId`, `name` (driver point name), `label`, `units`, `kind` (`analog` | `binary`), `adjustable`, optional `graphicGroup`.
- **`alarm_definitions`**: array of rules. Supported `conditionType` values in the agent today: `greaterThanSetpointPlusOffset` (needs `referencePointId` and `offset`), `boolFalse`.

Copy `volttron_data/ben_bacnet/app8_web_agent/site_model.example.json` as a starting point and align names with your Platform Driver registries.

Optional config keys:

- **`default_trend_point_id`**: first trend shown in the UI / API default.
- **`bacnet_devices`**: overrides the default list taken from all device keys in the site model (useful if the edge should only subscribe to a subset).

## 4. OAT share and other small agents

Any agent that references device or point names must use the **same identities** as Platform Driver. After renaming devices, update `oat_share_agent` config (or equivalent) so source and target device ids and point names match the live plant.

## 5. Deploy scripts from a Windows workstation

`deploy-app8-to-bosspi.ps1` and `deploy-oat-share-to-bosspi.ps1` accept parameters so you can target another host or tree without editing the file:

```powershell
.\deploy-app8-to-bosspi.ps1 -SshTarget 'user@10.0.0.50' -RemoteVolttronRoot '/home/user/volttron'
```

Defaults match the original bench layout.

## 6. Checklist before go-live

1. From the edge shell: `vctl status` — Platform Driver and `ben.app8.web` (or your identity) **running**.
2. `curl -sS http://127.0.0.1:8080/app8/api/health` (adjust port/prefix) — `counts.devices` / `points` non-zero when the model is loaded.
3. BACnet **who-is / read** from the same interface the driver uses (firewall and binding).
4. Journald / SD card: follow Pi logging guidance in `docs/bas-lite-app8-tutorial.md` (§8).

## 7. Non-BACnet drivers

The UI and site model are **driver-agnostic**: anything exposed through the Platform Driver RPC and publish contract can use the same `devices` / `points` metadata. BACnet is the reference implementation in this repo; Modbus, SNMP, or custom drivers follow the same pattern as long as device ids and point names match.
