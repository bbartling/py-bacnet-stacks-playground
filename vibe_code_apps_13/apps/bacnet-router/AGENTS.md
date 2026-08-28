# Phase 3 Router Agent Rules

Read the root `AGENTS.md`, `docs/PHASE_3_ROUTER_WEB_APP.md` and the clause checklist first.

## Hard identity

This is an NPDU router plus management appliance. Its MS/TP port participates as a master router address but is not the Phase 2 application device. Do not import or expose the Phase 2 AI/BI/AV/BV database.

## Integration rules

- Reinspect and prefer the pinned `AnyTransport` mixed-port implementation.
- Keep data-plane/router tasks independent of HTTP, disk and telemetry consumers.
- Add standard-frame routing tests first, but hard-cap them.
- Implement and independently test types 32/33, COBS and CRC-32K before claiming 135-2020 routing conformance.
- Build read-only telemetry/API only after the routed acceptance suite passes.
- Build config writes/authentication after the read-only UI.

## Definition of done

All router controls and application traffic pass through the same-PC topology, genuine extended frames interoperate, fault/soak evidence is retained, and the web process cannot block forwarding.

