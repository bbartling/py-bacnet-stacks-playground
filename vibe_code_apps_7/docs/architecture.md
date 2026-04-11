# App 7 architecture - BMS/BAS Lite

## Intent

Build a slim operator-facing BAS/BMS Lite app for Raspberry Pi-class deployments, using VOLTTRON as middleware instead of using VOLTTRON Central as the product UI.

## Design principles

- BACnet-first
- small-system friendly
- SD-card-aware logging and retention
- explicit API boundary between UI and runtime
- easy to teach, recreate, and evolve
- Open-FDD-inspired frontend feel without dragging in unnecessary complexity

## Layered architecture

## 1) Frontend

A React-based UI focused on operations visibility and control.

Primary responsibilities:

- show device tree and point inventory
- show live-ish point values / freshness / status
- show trends over short windows
- show alarms, alarm severity, and acknowledgement state
- manage alarm rules/configuration
- show notification configuration and send logs
- surface basic health state for the app/runtime

Frontend should talk only to the app backend, not directly to VOLTTRON.

## 2) App backend / API

A lightweight application service between frontend and runtime.

Primary responsibilities:

- expose stable UI-facing endpoints
- normalize device/point metadata
- manage polling state and write intent where allowed
- own alarm definitions and alarm-event lifecycle
- expose trend query endpoints
- store notification config and send history
- enforce retention/cleanup policy
- provide health/status summary for UI

This backend is the product boundary.

## 3) VOLTTRON layer

Primary responsibilities:

- BACnet Proxy
- Platform Driver
- scrape/publish pipeline
- supervisory agents
- reusable building/process logic

The VOLTTRON layer should be treated as runtime integration infrastructure, not the final operator-facing application.

## Data flow

1. BACnet devices are discovered/configured through the VOLTTRON integration path.
2. Driver/scrape paths publish current values into the runtime.
3. The app backend ingests, caches, or queries current values as needed.
4. Alarm evaluation uses backend-owned definitions with VOLTTRON-backed point data.
5. UI reads the backend API for inventory, current state, alarms, trends, and notification history.

## Storage posture

Separate storage classes on purpose:

### Current-state cache

- latest point values
- device freshness / heartbeat
- runtime health summary
- keep lightweight and replaceable

### Short-term trends

- recent time series for operator graphs
- bounded retention
- likely rollups/downsampling later

### Alarm/event history

- active alarms
- transitions
- acknowledgements
- notification attempts/results

### Config/state

- device metadata overrides
- polling enabled/disabled state
- alarm definitions
- retention config
- SMTP / notification config

## Raspberry Pi / SD-card posture

To reduce wear:

- avoid unbounded local logging
- keep verbose/debug logs off by default
- prefer bounded retention and rotation
- document journald limits explicitly
- distinguish operator history from developer/debug history
- keep trend retention configurable by deployment size

## MVP operator workflows

### Inventory view

- see devices
- expand devices into points
- see comm status/freshness
- enable/disable polling where appropriate

### Alarm workflow

- define alarm rules
- view active alarms
- acknowledge alarms
- inspect event history
- review notification attempts

### Trend workflow

- select point
- select recent time window
- view short-term trend
- later compare multiple points if needed

## Suggested implementation order

1. define backend contract
2. build frontend shell with mock data
3. define alarm schema/state model
4. implement backend inventory + alarm endpoints
5. implement short-term trend path
6. wire real VOLTTRON-backed data in carefully

## Open questions to settle later

- exact backend framework (FastAPI is a natural fit, but not mandatory)
- exact frontend component stack
- whether trend storage should start as SQLite-only or use a separate TS store
- whether alarm evaluation lives entirely in backend or partly in VOLTTRON agents
- whether writes/commands are in scope for MVP or read-mostly first
