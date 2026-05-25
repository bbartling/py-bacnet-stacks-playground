# Phase notepad — demo / bens-office (agent contract)

Human fills § A–D; agent reads **before** changing bind, `points.csv`, or IoT policy.

## § A — BACnet bind (head-end on Pi)

| Field | Value |
|-------|--------|
| Pi IP | `192.168.204.12` |
| Edge bind | `192.168.204.12/24:47809` (Vibe12Edge) |
| PiTemp local | UDP `47808` |
| MS/TP router | `192.168.204.200` · net `2000` |
| Target device | instance **5007** |

## § B — Building scope

| Field | Value |
|-------|--------|
| site_id | `demo` |
| building_id | `bens-office` |

## § C — Staged devices / points

Source: `commissioning/demo/bens-office/points.csv` (4 BACnet points enabled).

| point_id | BRICK class | Notes |
|----------|-------------|--------|
| `5007-analog-input-10014` | Zone_Air_Temperature_Sensor | STAT ZN-T (MSTP) |
| `5007-analog-input-1192` | Discharge_Air_Temperature_Sensor | DUCT-T |
| `5007-analog-input-1168` | Outside_Air_Humidity_Sensor | OA-H |
| `5007-analog-input-1173` | Outside_Air_Temperature_Sensor | OA-T |
| `digital-temp-degC` / `digital-temp-degF` | Zone_Air_Temperature_Sensor | GPIO DS18B20 · system `office` |

## § D — Dial-in URLs

| Surface | URL |
|---------|-----|
| Cloud dashboard | See `aws_cloud_pipeline/DEPLOYED.md` → DashboardUrl |
| Pi SSH | `ben@192.168.204.12` |

## § E — Phase strip

| Phase | Status | Next |
|-------|--------|------|
| Edge deploy | done | Re-run Ansible after CSV changes |
| MQTT → IoT | done | Policy `vibe12/+/+/+/+/telemetry` |
| Cloud ingest | done | `cloud_ingest_ok` via API |
| BRICK model | in progress | Human + SparkQL validation |
| FDD go-live | pending | Rule Lab after BRICK sign-off |
