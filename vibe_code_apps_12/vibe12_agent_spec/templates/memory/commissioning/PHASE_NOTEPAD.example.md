# Phase notepad — _(site_id / building_id)_

Human fills § A–D; agent reads **before** changing bind, `points.csv`, or IoT policy.

## § A — BACnet bind (head-end)

| Field | Value |
|-------|--------|
| Gateway IP | |
| Edge bind | `IP/prefix:udp_port` |
| MS/TP router (if any) | |
| Target device instance(s) | |

## § B — Building scope

| Field | Value |
|-------|--------|
| site_id | |
| building_id | |

## § C — Staged devices / points

Source: `commissioning/{site}/{building}/points.csv`

| point_id | BRICK class | Notes |
|----------|-------------|--------|
| | | |

## § D — Dial-in URLs

| Surface | URL |
|---------|-----|
| Cloud dashboard | |
| Gateway SSH | |

## § E — Phase strip

| Phase | Status | Next |
|-------|--------|------|
| Edge deploy | | |
| MQTT → IoT | | |
| Cloud ingest | | |
| BRICK model | | |
| FDD go-live | | |
