# Public offline inputs

[Course index](../INDEX.md) · [Wire contracts](../WIRE_FORMATS.md)

These are **synthetic, offline fixtures**, not captures from your bench. They can be opened/read without sending packets. No fixture generator or complete parser solution is supplied in the lesson path.

- [Day 19 text inputs](day19/README.md): valid, empty, malformed and invalid UTF-8 files.
- `teaching-envelope.hex`: the documented Day 36 known-answer message.
- `synthetic-ethernet.pcap`: four Ethernet-link-type records: IPv4/UDP teaching message, IPv4/UDP BACnet Who-Is, IPv6/UDP teaching message, and an isolated IPv4/TCP SYN. Timestamps are invented; the SYN is not a completed handshake. Frames omit FCS and may omit minimum-size Ethernet padding as host captures can. They are header-decoding inputs, not physical-wire measurements.
- `expected-packets.json`: public field expectations for the PCAP.
- [DNS](dns/README.md): a query, a compressed response and an invalid pointer cycle.
- [Modbus](modbus/README.md): TCP request/response/exception and an RTU CRC vector.
- [BACnet](bacnet/README.md): discovery/network-message bytes and an explicitly scoped segmentation event model.
- [DHCP](dhcp/README.md): a synthetic Discover payload.

`.hex` files contain whitespace-separated byte values. Decode them as bytes before using a binary parser. They contain no Ethernet header unless explicitly stated. For capture inspection, `tcpdump -nn -vv -r fixtures/synthetic-ethernet.pcap` works from the lessons directory when tcpdump is installed. Wireshark may show protocol dissectors differently by version; compare actual header fields.

`manifest.json` records SHA-256 hashes of public fixture data. Known-answer outputs are public contracts, not private grading answers. Add your own truncation, length, duplicate and timeout test cases in your learning workspace. Real serial timing and live interop remain separate labs.
