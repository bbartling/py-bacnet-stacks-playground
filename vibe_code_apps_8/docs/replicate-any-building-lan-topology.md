# Recreating BAS Lite (App 8) on any HVAC OT LAN

This note is for operators and integrators who need the same App 8 BAS Lite edge stack on a different site, VLAN, or BACnet plant layout. Nothing here assumes a particular bench hostname or IP range.

## 1. What must stay aligned

| Layer | What to configure |
|--------|-------------------|
| **Network** | Edge host can reach field controllers on the BACnet / OT VLAN (routing, ACLs, BBMD if used). |
| **BACnet** | diy-bacnet binds **UDP 47808** on the host (only one listener per host). JSON-RPC is published separately (see **`.env.example`**). |
| **Driver / supervisor** | Device and point definitions under **`BAS_LITE_DRIVER_CONFIG_DIR`** (SQLite + JSON) must match what easy-aso polls and what the React UI lists. |
| **App 8 API/UI config** | Alarms, notifications, **schedule JSON** (`/data/schedule.json` by default), and optional **`hostedScheduleName`** for BACnet schedule push. |
| **Reverse proxy** | Caddy upstream URL, Basic Auth secrets, TLS policy. See `docker/caddy/`. |

## 2. Device and point identities

The runtime polls configured devices and points using the **easy-aso** supervisor configuration.

- Use **stable string identities** that match your driver JSON (often the same as the logical device folder name).
- Prefer a naming convention that scales: `campus/building/ahu_01` or `SITE_AHU01` — avoid embedding IP addresses in the identity unless that is already your standard.

## 3. Site model (no Python edits for a new building)

Describe equipment and points in JSON instead of editing bespoke agent code.

**Option A — external file** (next to the supervisor data path or absolute path):

```json
{
  "site_model_path": "site_model.json"
}
```

**Option B — inline** in `config`: top-level keys `devices`, `points`, optional `alarm_definitions`.

Schema summary:

- **`devices`**: object keyed by device id; each value may include `displayName`, `kind`, `address`, BACnet `deviceId`, `pollingEnabled`, etc.
- **`points`**: array of objects with `pointId`, `deviceId`, `name` (driver point name), `label`, `units`, `kind` (`analog` | `binary`), `adjustable`, optional `graphicGroup`.
- **`alarm_definitions`**: array of rules. Supported `conditionType` values in the supervisor today: `greaterThanSetpointPlusOffset` (needs `referencePointId` and `offset`), `boolFalse`.

Copy the local site model example used by your current deployment and align names with your BACnet plant.

Optional config keys:

- **`default_trend_point_id`**: default trend point for API defaults.
- **`bacnet_devices`**: overrides the default list taken from all device keys in the site model (useful if the edge should only subscribe to a subset).

## 4. Occupancy schedule + optional BACnet sidecars

- **Schedule UI** stores **`version` 2** JSON with `schedules[]`, weekly `mon`…`sun` windows, holiday overrides, equipment **`assignments`**, optional **`bacnetBindings`** (rows reference **supervisor `pointId`** values from your driver setup), and **`hostedScheduleName`** for diy-bacnet `server_update_schedule`. Use **Export JSON** / **AI-assisted import** on the Occupancy page for bulk edits.
- **Outside-air (legacy helper):** Compose profile **`oat`** → **`easy-aso-oat`**. Reads one BACnet object, writes **`OAT_TARGET_WRITES`** over JSON-RPC (no second **UDP 47808**).
- **Multi-agent EasyASO:** profile **`agents`** → **`easy-aso-agent-oat`**, **`easy-aso-agent-gl36-vav`**, **`easy-aso-agent-gl36-ahu`** ( **`easy-aso[platform]==0.1.7`**, **`easy-aso-agent run`**, **`RpcDockedEasyASO`**). Building-agnostic JSON in **`.env`** (**`EASY_ASO_GL36_VAV_CONFIG`**, **`EASY_ASO_GL36_AHU_CONFIG`**, **`OAT_*`**). Optional fourth service: merge **`docker-compose.easy-aso-agents.example.yml`**. Details: **`docs/BOSS_PI_BAS_LITE_DOCKER.md`** §9.

## 5. Deploy scripts from a Windows workstation

**`sync-bas-lite-to-bosspi.ps1`** (or **`deploy-app8-to-bosspi.ps1`**) — same **Pi-first defaults**: SD-friendly bootstrap, PC **`npm run build`** + synced **`frontend/dist`** (Pi skips in-Docker Vite unless you opt out). Target another host:

```powershell
.\sync-bas-lite-to-bosspi.ps1 -Target 'user@10.0.0.50'
.\deploy-app8-to-bosspi.ps1 -SshTarget 'user@10.0.0.50'
```

**`-SyncOnly`** — copy files only; run **`./scripts/bootstrap-bas-lite.sh`** on the edge yourself. **`-SdFriendly:$false`** / **`-PrebuiltFrontend:$false`** — power-user overrides.

Pi bootstrap: **`./scripts/bootstrap-bas-lite.sh`** (flags in **`--help`**).

## 6. Checklist before go-live

1. From the edge shell: `docker compose ps` and `docker compose logs --tail=100 api diy-bacnet caddy frontend` (add **`easy-aso-agent-*`** services if profile **`agents`** is enabled).
2. `curl -sS http://127.0.0.1:8080/app8/api/health` (adjust port/prefix) — `counts.devices` / `points` non-zero when the model is loaded.
3. BACnet **who-is / read** from the same interface the driver uses (firewall and binding).
4. Journald / SD card: follow Pi logging guidance in `docs/BOSS_PI_BAS_LITE_DOCKER.md` (§5).

## 7. Non-BACnet drivers

The UI and site model are **driver-agnostic**: anything exposed through the selected backend contract can use the same `devices` / `points` metadata. BACnet is the reference implementation in this repo; Modbus, SNMP, or custom drivers follow the same pattern as long as device ids and point names match.
