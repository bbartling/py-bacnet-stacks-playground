# Day 98 — Week 14 Review — Pi pocket router and WAP

[Previous: Day 97](day97.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 99](day99.md)

**Week 14 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–97, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Assemble a portable lab network with a Pi, a client LAN/WAP, an uplink and your Rust TCP traffic switch/diagnostics. Use OS-supported services for DHCP/DNS/NAT. The Rust deliverables are the traffic switch, packet/lease inspection and bounded health tooling. Writing a Wi-Fi driver or DHCP server is outside scope.

Environment: Dedicated Pi lab or the explicitly labeled VM/offline alternative. Hardware results must come from the actual hardware. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Document actual hardware, interface roles, non-overlapping prefixes and management recovery.
- Two clients receive valid leases, query the intended DNS service and reach an allowed upstream service.
- A proxy-routed TCP exchange preserves bytes and half-close behavior.
- Uplink loss is reported distinctly from LAN failure; reboot recovery matches the runbook.
- DHCP remains confined to the lab LAN, and firewall/service ownership is explicit.
- USB claims refer to USB network interfaces; RS-485 devices are not assigned IP leases.

## Deliverables

- Topology, service/profile configuration with secrets removed, deployed Rust versions and rollback instructions.
- Association/link, DHCP, DNS, routing and proxy evidence with packet references.
- Failure/reboot results; label radio or physical tests pending if only the VM track was completed.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Which behavior came from Linux/network services and which came from your Rust programs?
- Can someone else recover management without knowing the current DHCP lease?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-14); references may contain examples, so attempt the review independently first.

[Previous: Day 97](day97.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 99](day99.md)
