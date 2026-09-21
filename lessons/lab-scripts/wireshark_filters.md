# Capture and display filters for Days 1–112

[Course index](../INDEX.md) · [Lab guide](../LAB_GUIDE.md)

A **capture filter** uses BPF and limits what gets saved. A **display filter** uses Wireshark syntax and changes what you see afterward. tcpdump accepts the capture expression as a final quoted argument; `-f` is not a general “filter expression” flag. Replace example ports and addresses with the actual lab values.

| Days | Capture filter example | Wireshark display filter | Question |
| --- | --- | --- | --- |
| 29–31, 35 | `arp or icmp` | `arp or icmp` | Which neighbor or next hop is involved? |
| 32–35 | `icmp6` | `icmpv6` | Neighbor discovery, RA or packet-too-big? |
| 34, 46, 95 | `port 53` | `dns` | Was a DNS query actually emitted? |
| 36–42 | `ip or ip6 or arp` | `ip or ipv6 or arp` | Which headers and lengths are present? |
| 43–49 | `udp port 40000` | `udp.port == 40000` | Which request/peer produced the reply? |
| 50–63 | `tcp port 40001 or tcp port 40002` | `tcp.port == 40001 or tcp.port == 40002` | What happened to each TCP connection? |
| 64–70 | `tcp port 1502 or tcp port 502` | `modbus or tcp.port == 1502` | How do MBAP boundaries compare with reads? |
| 71–91, 108 | `udp port 47808` | `udp.port == 47808` | Which BVLC/NPDU/APDU path is visible? |
| 94, 98 | `udp port 67 or udp port 68` | `udp.port == 67 or udp.port == 68` | Initial lease or renewal? |
| 96–98 | `host 192.168.77.20` | `ip.addr == 192.168.77.20` | What changes between LAN and uplink? |
| 109 | `tcp port 8080 or tcp port 443` | `http or tls or websocket` | Which management exchange is visible? |

Protocol display filters depend on dissector recognition. For a nonstandard Modbus port, use **Analyze → Decode As** when appropriate and record that setting. A port filter matches traffic regardless of whether the dissector recognizes it. On routed/NAT captures, a LAN address filter may miss the translated uplink side: select each capture point's actual addresses.

For one TCP conversation, select a packet and use Follow TCP Stream, then note the actual `tcp.stream` value. Stream numbers are local to a capture. Follow TLS Stream does **not** magically decrypt TLS; authorized session secrets and supported conditions are needed. Do not include secrets in shared fixtures.

## Bounded capture helper

From the repository root:

```bash
PCAP_IFACE=lo PCAP_SECONDS=15 PCAP_COUNT=200 lessons/lab-scripts/capture_pcap.sh udp-echo 'udp port 40000'
```

The helper records at most a chosen duration and packet count, with a bounded snap length. It defaults to Linux `any`, which may produce cooked capture records. Use an explicit Ethernet interface when comparing Ethernet headers. Default snap length is 2048; increase it deliberately for larger frames and check captured-versus-original lengths. A truncated capture is not proof that a sender emitted a short packet.

The helper requires tcpdump, GNU timeout and permission to capture. It runs capture only when you invoke it; none of the live labs were run as part of authoring the lessons. See [VALIDATION.md](../VALIDATION.md).

## A useful capture note

Record command, capture/display filters, interface and link type, tool versions, frame numbers, expected/observed behavior and limitations. Prefer a short trace of one controlled interaction to a large unexplained capture. Ethernet capture cannot see RS-485 electrical traffic; serial lessons need appropriately sourced serial evidence.
