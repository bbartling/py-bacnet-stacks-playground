## Day 35 – Network Programming Map (UDP, TCP, Ports)

### Goal

Place **BACnet/IP**, **Haystack HTTPS**, and **Modbus TCP** on the same mental map you would see in a university networking course—before writing sockets.

### Concept

| Protocol | Transport | Typical port | Building use |
|----------|-----------|--------------|--------------|
| BACnet/IP | **UDP** | 47808 | Who-Is, ReadProperty, COV |
| Haystack REST | **TCP** + TLS | 443 | `/about`, `/read`, `/ops` |
| Modbus TCP | **TCP** | 502 / 1502 | Register reads |

**UDP**: connectionless datagrams—fast, no guaranteed delivery (fine for BACnet with app-layer retries).

**TCP**: reliable byte stream—HTTP sits on top.

Your bench (example):

- Edge: `192.168.204.55`
- BACnet device: `192.168.204.200:47808/udp`
- Niagara nHaystack: `https://192.168.204.11/haystack`

### Why This Matters

When Wireshark shows "UDP" vs "TCP", you know **which stack** you are debugging—BACnet driver vs Haystack client.

### Mini examples

- Sketch a diagram: Pi → UDP → BACnet device; Pi → TCP → Niagara.
- List three reasons BACnet chose UDP historically (broadcast, low overhead, LAN-local).

### Micro exercises

1. What port does `ss -ulnp | grep 47808` show on a BACnet gateway?
2. Why is Haystack not "just another UDP app"?
3. Write one sentence linking Day 33 `HashMap` to caching I-Am responses.

### Key takeaway

**Pick transport by protocol spec**, not preference—rusty-bacnet speaks UDP; rusty-haystack speaks HTTP over TCP.

### Wireshark Lab

Open an empty capture mindset: **Statistics → Protocol Hierarchy** on any future pcap—that's your course dashboard.
