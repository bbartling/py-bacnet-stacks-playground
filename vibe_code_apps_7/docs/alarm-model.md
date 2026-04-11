# Alarm model draft

This file defines the first-pass alarm model for app 7.

## Goals

- understandable to an operator
- simple enough for an MVP
- extensible later for richer logic
- clearly separate alarm definition from alarm event

## Core concepts

## Alarm definition

An alarm definition describes *what should be watched* and *when an event should fire*.

Suggested fields:

- `id`
- `name`
- `enabled`
- `deviceId`
- `pointId`
- `severity` (`info`, `warning`, `critical`)
- `conditionType`
- `condition`
- `messageTemplate`
- `deadband`
- `persistenceSeconds`
- `autoClear`
- `notifyChannels`
- `createdAt`
- `updatedAt`

### Candidate condition types

- `greaterThan`
- `greaterThanOrEqual`
- `lessThan`
- `lessThanOrEqual`
- `equal`
- `notEqual`
- `stale`
- `outOfRange`
- `boolTrue`
- `boolFalse`

## Alarm event

An alarm event is a runtime occurrence created when a definition transitions into alarm.

Suggested fields:

- `id`
- `alarmDefinitionId`
- `deviceId`
- `pointId`
- `state` (`active`, `acknowledged`, `cleared`)
- `severity`
- `message`
- `triggeredAt`
- `acknowledgedAt`
- `acknowledgedBy`
- `clearedAt`
- `lastObservedValue`
- `lastObservedQuality`
- `notificationStatus`

## State transitions

Basic lifecycle:

1. definition condition becomes true
2. backend waits optional persistence period
3. event becomes `active`
4. operator may acknowledge -> `acknowledged`
5. condition clears -> event becomes `cleared`

Acknowledged alarms may still remain visually active until the condition clears.

## Suggested MVP rule types

Start with a small set:

- high limit
- low limit
- stale/no-update
- binary fault state
- out-of-range

This covers a lot of BAS-lite value without overbuilding.

## Noise control

To avoid alarm spam:

- use persistence timers
- use deadbands for analog thresholds
- avoid repeated notifications on every scrape
- support notification-on-enter and optional reminder-on-still-active later

## Notification linkage

Alarm definitions should include desired notification routing metadata, but notification delivery results belong on alarm events / notification logs.

## Example definition

```json
{
  "id": "alarm-zone1-temp-high",
  "name": "Zone 1 temperature high",
  "enabled": true,
  "deviceId": "zone1-vav",
  "pointId": "zone1-space-temp",
  "severity": "warning",
  "conditionType": "greaterThan",
  "condition": { "threshold": 78.0 },
  "deadband": 1.0,
  "persistenceSeconds": 300,
  "autoClear": true,
  "notifyChannels": ["smtp"]
}
```

## Example event

```json
{
  "id": "evt-0001",
  "alarmDefinitionId": "alarm-zone1-temp-high",
  "deviceId": "zone1-vav",
  "pointId": "zone1-space-temp",
  "state": "active",
  "severity": "warning",
  "message": "Zone 1 temperature high",
  "triggeredAt": "2026-04-11T06:15:00Z",
  "lastObservedValue": 79.3,
  "notificationStatus": "sent"
}
```

## Future expansions

Later, this model can grow into:

- schedules / occupied vs unoccupied logic
- multi-point compound conditions
- delayed clear behavior
- escalation chains
- shelving/suppression
- maintenance overrides
- fault-rule templates by equipment type
