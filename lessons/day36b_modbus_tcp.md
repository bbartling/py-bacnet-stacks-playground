# Day 36b – Modbus TCP (beginner OT over TCP)

**Supplement after Day 36.** Modbus is the **easiest building-automation wire protocol** to learn after raw UDP/TCP sockets: one **TCP connection**, simple **request/response** frames, no broadcast, no object model like BACnet.

### Goal

Read a **holding register** from a Modbus/TCP device with a minimal Rust client—or understand the bytes before using a production driver (e.g. Open-FDD Modbus).

### Concept

| Item | Modbus TCP | BACnet/IP (contrast) |
|------|------------|----------------------|
| Transport | **TCP** | **UDP** |
| Typical port | **502** (or **1502** on lab PLCs) | **47808** |
| Addressing | **Unit ID** + register number | Device instance + object type + property |
| Frame shape | MBAP header + PDU | BVLC + NPDU + APDU |
| Beginner friendly | **Yes** — read reg 40001 | Harder — Who-Is, ReadProperty |

**Function codes (most common):**

- **3** — Read Holding Registers (4xxxx)
- **4** — Read Input Registers (3xxxx)

**Bench example (Open-FDD lab):** `192.168.204.14:1502`, unit **1**, temp often in holding register map.

### Mental model

```text
Your Rust program  --TCP connect-->  Modbus device :1502
                  --send ADU------>  [unit][func][addr][count]
                  <--response-------  [bytes... register values]
```

No TLS, no HTTP headers—just length-prefixed binary after the MBAP header.

### Mini Rust sketch (educational)

Use **`tokio-modbus`** or raw `TcpStream` + manual ADU for learning:

```rust
// Pseudocode — see capstone/modbus-read/ for a clap starter
// 1. TcpStream::connect("192.168.204.14:1502")
// 2. Build Modbus TCP frame: transaction id, unit id=1, func=3, start=0, count=1
// 3. Read response; decode u16 register; apply scale (e.g. ÷10 for °F)
```

Compare to Day **37** generic TCP echo—Modbus adds **structure** inside the byte stream.

### Why this matters

- Most VFDs, power meters, and lab PLCs speak Modbus before BACnet.
- **Open-FDD** Modbus driver polls the same pattern at the edge.
- Wireshark can decode Modbus when you outgrow printf debugging.

### Micro exercises

1. Telnet/`nc` to port 1502—why does binary garbage appear? (Modbus is not ASCII.)
2. Given register value `753`, scaled ÷10 → **75.3 °F**—where would you store scale in config?
3. Why is Modbus **easier to capture** than BACnet in Wireshark? (TCP stream, no UDP broadcast.)

### Key takeaway

**Modbus = TCP + simple register map.** Master BACnet only after you are comfortable with **Day 36 UDP** and **Day 37 TCP**, plus this register read pattern.

### Wireshark Lab

Capture filter:

```bash
cd lessons/lab-scripts
./capture_pcap.sh day36b-modbus "tcp port 1502 or tcp port 502"
```

Display filter: **`modbus`** or **`tcp.port == 1502`**

Expand the **Modbus** section in packet details—note **Transaction ID**, **Unit ID**, **Function code**.

### Next

- Day **37** — generic TCP echo (HTTP foundation)
- Day **39** — BACnet on UDP (harder OT)
- [capstone/modbus-read/](../capstone/modbus-read/) — optional CLI starter
