# Phase 3 — BFR router research notes (design only)

[BFR](https://bfr.sourceforge.net/) is a BACnet/IP router/firewall. **It does not implement MS/TP.** Do not add it as a Phase 2 dependency.

## Ideas to reuse in Phase 3 Vibe13 router work

- Adapter-based multi-network routing fixtures (virtual LAN + injected NPDUs)
- Route/filter expectation tests (allowed/denied NPDU forwarding)
- Hop-count and loop-prevention test vectors
- Firewall-style service/network rules as documentation-driven tests

## Out of scope for Phase 2 PR #127

- BACnet/IP stack in the mini-device
- BBMD/NAT/firewall appliance code
- BFR binary or config import

Phase 3 router remains a separate role from the Phase 2 MS/TP mini-device.
