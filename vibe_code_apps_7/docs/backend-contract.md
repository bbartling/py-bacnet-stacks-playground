# Backend contract draft

This is the UI-facing contract for app 7.

The purpose is to keep the frontend stable even if the VOLTTRON-side integration evolves.

## Principles

- frontend talks only to backend
- backend returns operator-friendly shapes
- backend owns alarm/event semantics
- backend normalizes data freshness/status
- API should be small before it becomes clever

## Core resources

- `/api/health`
- `/api/devices`
- `/api/devices/:deviceId`
- `/api/points`
- `/api/points/:pointId`
- `/api/polling`
- `/api/alarms/definitions`
- `/api/alarms/events`
- `/api/trends`
- `/api/notifications/config`
- `/api/notifications/logs`
- `/api/setpoints`
- `/api/setpoints/write`

## Health

### `GET /api/health`

Returns:

- app status
- backend uptime
- last successful VOLTTRON sync / scrape visibility
- counts for devices, points, active alarms
- storage/retention summary

Example:

```json
{
  "status": "ok",
  "backendTime": "2026-04-11T06:00:00Z",
  "volttron": {
    "status": "connected",
    "lastSync": "2026-04-11T05:59:52Z"
  },
  "counts": {
    "devices": 2,
    "points": 24,
    "activeAlarms": 1
  }
}
```

## Devices

### `GET /api/devices`

List devices for the device tree.

Example fields:

- `id`
- `name`
- `network`
- `address`
- `status`
- `lastSeen`
- `pollingEnabled`
- `pointCount`

### `GET /api/devices/:deviceId`

Returns one device plus point summaries.

## Points

### `GET /api/points`

Filterable point list for point table.

Suggested filters:

- `deviceId`
- `kind`
- `status`
- `alarmState`
- `search`

Point fields:

- `id`
- `deviceId`
- `name`
- `objectType`
- `objectInstance`
- `units`
- `value`
- `quality`
- `lastUpdated`
- `alarmState`
- `trendEnabled`

### `GET /api/points/:pointId`

Returns full point detail.

## Polling state

### `GET /api/polling`

Returns polling status/summary for devices and points.

### `PATCH /api/polling/devices/:deviceId`

Example body:

```json
{ "pollingEnabled": true }
```

### `PATCH /api/polling/points/:pointId`

Example body:

```json
{ "pollingEnabled": false }
```

## Alarm definitions

### `GET /api/alarms/definitions`

Lists alarm rules.

### `POST /api/alarms/definitions`

Creates a new rule.

### `PATCH /api/alarms/definitions/:alarmDefinitionId`

Updates a rule.

### `DELETE /api/alarms/definitions/:alarmDefinitionId`

Disables/removes a rule depending on product choice.

## Alarm events

### `GET /api/alarms/events`

Lists active/recent alarm events.

Suggested filters:

- `state=active|cleared|acked`
- `severity`
- `deviceId`
- `pointId`
- `from`
- `to`

### `POST /api/alarms/events/:eventId/ack`

Acknowledges an alarm event.

## Trends

### `GET /api/trends`

Query parameters:

- `pointId`
- `from`
- `to`
- `bucket`

Response should return a small, chart-friendly time-series payload.

## Notifications

### `GET /api/notifications/config`
### `PUT /api/notifications/config`

Store SMTP/notification config.

### `GET /api/notifications/logs`

List notification attempts/results.

Fields might include:

- `timestamp`
- `channel`
- `recipient`
- `eventId`
- `status`
- `error`

## Initial implementation guidance

For the first pass:

- build these routes as live in-memory-backed endpoints over the 2-device bench data
- keep response shapes stable
- avoid overcommitting to internal implementation too early
- allow OpenClaw chat to act as the practical operator/config layer for alarm/trend setup during early bench work
- keep the browser UI lighter and simpler than the API surface
