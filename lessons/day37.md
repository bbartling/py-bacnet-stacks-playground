## Day 37 – TCP Client & Server (Mini Echo)

### Goal

Build a **TCP echo** client and server—foundation for understanding HTTP/TLS sessions to Haystack.

### Concept

Server sketch (`TcpListener`):

```rust
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
fn handle(mut stream: TcpStream) -> std::io::Result<()> {
    let mut buf = [0u8; 1024];
    let n = stream.read(&mut buf)?;
    stream.write_all(&buf[..n])?;
    Ok(())
}
fn main() -> std::io::Result<()> {
    let listener = TcpListener::bind("127.0.0.1:7777")?;
    for stream in listener.incoming() {
        handle(stream?)?;
    }
    Ok(())
}
```

Client: `nc 127.0.0.1 7777` or a 10-line `TcpStream::connect` program.

### Why This Matters

Haystack `/read` is **HTTP over TCP**. If TCP confuses you, TLS and JSON responses will too.

### Mini examples

- Log peer address with `stream.peer_addr()?`.
- Send HTTP-ish line by hand: `GET / HTTP/1.0\\r\\n\\r\\n` to a public test server (lab only).

### Micro exercises

1. Compare UDP Day 36 vs TCP Day 37: what shows up in Wireshark differently?
2. Handle multiple clients (hint: `thread::spawn` one connection)—optional stretch.
3. Why does BACnet *not* use this pattern for field traffic?

### Key takeaway

TCP = **connected byte stream**. HTTP requests are text (or binary HTTP/2) inside that stream.

### Wireshark Lab

Capture while running echo:

```bash
./capture_pcap.sh day37-tcp-echo "tcp port 7777"
```

Display filter: **`tcp.port == 7777`**

Look for **SYN, SYN-ACK, ACK** handshake before your payload.
