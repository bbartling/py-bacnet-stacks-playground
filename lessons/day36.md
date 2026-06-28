## Day 36 – UDP Sockets in Rust (Echo Lab)

### Goal

Send and receive a **UDP datagram** with `std::net::UdpSocket`—the same primitive BACnet/IP uses under BVLC.

### Concept

Terminal A (listener):

```rust
// udp_echo_server.rs — cargo new udp_lab
use std::net::UdpSocket;
fn main() -> std::io::Result<()> {
    let sock = UdpSocket::bind("127.0.0.1:9999")?;
    let mut buf = [0u8; 1024];
    let (n, src) = sock.recv_from(&mut buf)?;
    sock.send_to(&buf[..n], src)?;
    Ok(())
}
```

Terminal B: `echo hello | nc -u 127.0.0.1 9999`

### Why This Matters

Every BACnet BVLC packet starts as **bytes in a UDP payload**. Today you see the raw datagram before rusty-bacnet wraps it.

### Mini examples

- Bind `0.0.0.0:9999` vs `127.0.0.1:9999`—when is each appropriate?
- Print hex of first 4 bytes: `{:02x?}`, &buf[..4].

### Micro exercises

1. Modify server to uppercase ASCII payload before echo.
2. Capture your echo traffic (see Wireshark Lab).
3. What buffer size might BACnet frames need? (hint: ~1476 bytes MTU-ish)

### Key takeaway

**`recv_from` / `send_to`** — address + port per datagram. BACnet adds structure *inside* the payload.

### Wireshark Lab

```bash
cd lessons/lab-scripts
./capture_pcap.sh day36-udp-echo "udp port 9999"
```

Open the pcap → display filter: **`udp`**

Follow **UDP Stream** on your echo packet pair. Note: no handshake—one packet out, one back.
