#!/usr/bin/env python3
"""One-shot generator for Days 28–75 Rust networking course. Run from lessons/."""
from pathlib import Path

LESSONS = {
28: """## Day 28 – Install Rust & Cargo (Your First Binary)

### Goal

Install **Rust** and **Cargo**, create a project, and run `hello` on your edge PC—the same machine you used for Python BACnet labs.

### Concept

**Rust** compiles to a fast native binary with strong memory safety. **Cargo** is the build tool: it fetches crates (libraries), compiles, runs tests, and documents dependencies in `Cargo.toml`.

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustc --version && cargo --version
cargo new bacnet_lab --bin
cd bacnet_lab && cargo run
```

Project layout:

- `src/main.rs` — entry point (`fn main()`)
- `Cargo.toml` — name, version, dependencies

### Why This Matters

Field gateways and modern BAS edge stacks (Open-FDD, rusty-bacnet, rusty-haystack) ship as **compiled Rust services**, not interpreted Python scripts. Cargo is how you build them reproducibly on a Pi or Linux box.

### Mini examples

- Change `println!` to print your bench IP (`192.168.204.55`).
- Run `cargo build --release` and note where the binary lands (`target/release/`).

### Micro exercises

1. Install rustup and paste `rustc --version` output in your lab notes.
2. Create `bacnet_lab` and add a second `println!` with today's date.
3. Run `cargo check` vs `cargo build`—what is the difference in one sentence?

### Key takeaway

**Cargo new → cargo run** is the Rust equivalent of `python script.py`, but you get a standalone binary you can deploy on an edge host.
""",
29: """## Day 29 – Rust Types, Operators & Variables

### Goal

Learn Rust **scalars** (`i32`, `f64`, `bool`, `char`), **mutability**, and operators—enough to format BACnet-style readings in `println!`.

### Concept

```rust
fn main() {
    let device_id: u32 = 5007;
    let mut present_value: f64 = 72.5;
    present_value += 0.25;
    let online = true;
    println!("dev {} pv {:.1} online {}", device_id, present_value, online);
}
```

- **`let`** binds immutably unless you write **`mut`**
- Integer types: `u8`, `u16`, `u32`, `i32`, `usize`
- Floats: `f32`, `f64`
- Comparisons: `==`, `!=`, `<`, `>`, `&&`, `||`, `!`

### Why This Matters

BACnet object IDs and present values map cleanly to `u32` and `f64`. Explicit types prevent silent rounding bugs in control math.

### Mini examples

- Store OAT as `f64`, SAT as `f64`, compute delta.
- Use `{:.2}` formatting for trend-like output.

### Micro exercises

1. Declare `let port: u16 = 47808;` and print it (BACnet/IP default).
2. What happens if you try `present_value = 80.0` without `mut`? Read the compiler error.
3. Write an expression: `sat > 55.0 && oat < 40.0` as a `bool`.

### Key takeaway

Rust forces you to **choose numeric types** and **declare mutability**—annoying at first, invaluable when a gateway runs for months without restarts.
""",
30: """## Day 30 – Control Flow: if, loop, match

### Goal

Branch and iterate like Python `if`/`for`, but with **`match`** for exhaustive enum-style logic.

### Concept

```rust
fn classify_sat(sat: f64) -> &'static str {
    if sat > 55.0 {
        "high"
    } else if sat < 45.0 {
        "low"
    } else {
        "ok"
    }
}

fn main() {
    for i in 0..5 {
        println!("sample {}", i);
    }
    let code = 2;
    match code {
        0 => println!("normal"),
        1 | 2 => println!("warning"),
        _ => println!("unknown"),
    }
}
```

### Why This Matters

Control sequences are **state machines**. `match` makes BACnet priority levels and alarm severities explicit—compiler warns if you forget a case.

### Mini examples

- Loop over `[68.0, 71.0, 74.0]` and print `classify_sat` for each.
- Use `while` to simulate a 3-iteration poll loop.

### Micro exercises

1. Write `match` on priority `1..=16` that prints "manual" only for priority 8.
2. Convert a Python-style `for x in list` mental model: what is `0..3` vs `0..=3`?
3. Refactor nested `if` into `match` on a small enum you define.

### Key takeaway

**`match` is your friend** for BACnet enums (object types, error codes) later in rusty-bacnet labs.
""",
31: """## Day 31 – Functions, Option & Result

### Goal

Write reusable functions and handle **missing data** (`Option`) and **errors** (`Result`)—the Rust patterns every network client uses.

### Concept

```rust
fn parse_pv(text: &str) -> Result<f64, std::num::ParseFloatError> {
    text.trim().parse::<f64>()
}

fn first_ok(values: &[Option<f64>]) -> Option<f64> {
    values.iter().find_map(|v| *v)
}

fn main() {
    match parse_pv("72.5") {
        Ok(v) => println!("pv = {v}"),
        Err(e) => eprintln!("bad pv: {e}"),
    }
}
```

- **`Option<T>`**: `Some(x)` or `None`
- **`Result<T, E>`**: `Ok(x)` or `Err(e)`
- **`?` operator** (later): propagate errors up the call stack

### Why This Matters

A BACnet read can **timeout**, return **ERROR**, or give a value. Rust makes you handle that in the type system instead of `None` surprises at 2 a.m.

### Mini examples

- Function `c_to_f(c: f64) -> f64`
- Return `None` when a CSV field is empty string.

### Micro exercises

1. Write `fn device_label(id: u32) -> String` using `format!`.
2. Write `parse_u32(s: &str) -> Option<u32>`.
3. Explain in one sentence: when would you use `Option` vs `Result`?

### Key takeaway

Network code lives on **`Result`**. Get comfortable before UDP sockets and HTTP clients.
""",
32: """## Day 32 – struct, enum & impl

### Goal

Model a **BACnet point** as a `struct` and object kinds as an **`enum`**.

### Concept

```rust
#[derive(Debug, Clone)]
struct BacnetPoint {
    device_id: u32,
    object_type: u16,
    instance: u32,
    name: String,
}

enum ObjectKind {
    Ai,
    Ao,
    Av,
    Bi,
    Bo,
}

impl BacnetPoint {
    fn object_id(&self) -> String {
        format!("{}:{}", self.object_type, self.instance)
    }
}
```

### Why This Matters

rusty-bacnet and rusty-haystack expose **typed structs** for devices, tags, and reads. You will read `impl` blocks in their docs daily.

### Mini examples

- Add method `is_analog(&self) -> bool` using `ObjectKind`.
- Print `Debug` output with `{:?}`.

### Micro exercises

1. Define `struct Zone { name: String, temp_c: f64 }` with a method `fahrenheit`.
2. Enum `AlarmState { Normal, Offnormal, Fault }` with `match` printer.
3. Why does `#[derive(Debug)]` help when sniffing packets and logging?

### Key takeaway

**Structs hold data; enums restrict variants**—perfect for equipment models before RDF weeks.
""",
33: """## Day 33 – Vec, HashMap & String

### Goal

Use **`Vec`**, **`HashMap`**, and **`String`**—the collections you'll use to cache device lists and tag maps.

### Concept

```rust
use std::collections::HashMap;

fn main() {
    let mut readings: Vec<f64> = vec![71.2, 72.0, 71.8];
    readings.push(72.5);
    let mut by_device: HashMap<u32, String> = HashMap::new();
    by_device.insert(5007, "AHU-1".into());
    if let Some(name) = by_device.get(&5007) {
        println!("{name}: avg {:.2}", readings.iter().sum::<f64>() / readings.len() as f64);
    }
}
```

- **`String`** vs **`&str`**: owned vs borrowed text
- **`.iter()`**, **`.push()`**, **`.get()`**

### Why This Matters

Who-Is responses and Haystack `/read` results become **`HashMap` caches** on an edge agent.

### Mini examples

- Count how many readings exceed 72.0 using a loop (no itertools yet).
- Build `HashMap<&str, f64>` of sensor name → value from two parallel vectors.

### Micro exercises

1. Sort `readings` with `readings.sort_by(|a,b| a.partial_cmp(b).unwrap())`.
2. Remove a key from a map safely with `.remove`.
3. When would you store `String` keys vs `u32` device IDs?

### Key takeaway

**Vec + HashMap** replace Python lists and dicts—learn them before parsing network responses into memory.
""",
34: """## Day 34 – Ownership & Borrowing (Fast Track)

### Goal

Survive the **borrow checker** long enough to pass `&str` into functions and store data in structs without fighting the compiler.

### Concept

```rust
fn log_tag(tag: &str, val: f64) {
    println!("{tag} = {val}");
}

fn main() {
    let name = String::from("OA-T");
    log_tag(&name, 55.3);  // borrow &name as &str
    println!("still own {name}");
}
```

Rules (simplified):

1. One **mutable** borrow *or* many **immutable** borrows at a time
2. References must not outlive the data they point to
3. **`clone()`** when you truly need a copy

### Why This Matters

Socket buffers and HTTP bodies are **borrowed slices** (`&[u8]`, `&str`). Fighting ownership early makes rusty-bacnet examples click.

### Mini examples

- Fix a "borrow of moved value" compiler error by using `.clone()` or references.
- Function taking `&[f64]` instead of `Vec<f64>`.

### Micro exercises

1. Explain why `let s2 = s1; println!("{s1}")` fails for `String`.
2. Write `fn avg(vals: &[f64]) -> Option<f64>`.
3. Read one rusty-bacnet example; circle every `&` and `&mut` in comments.

### Key takeaway

**Borrow instead of clone** in hot paths (polling loops). Clone when building persistent caches.

### Wireshark Lab

No capture today—read [wireshark_filters.md](./lab-scripts/wireshark_filters.md) so Day 36 feels familiar.
""",
35: """## Day 35 – Network Programming Map (UDP, TCP, Ports)

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
""",
36: """## Day 36 – UDP Sockets in Rust (Echo Lab)

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
""",
37: """## Day 37 – TCP Client & Server (Mini Echo)

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
""",
38: """## Day 38 – tcpdump & PCAP Workflow

### Goal

Master the **capture → file → Wireshark** loop you'll reuse for BACnet and Haystack labs.

### Concept

```bash
# 30s BACnet bench capture (adjust host)
sudo tcpdump -i any -w bacnet.pcap -s 0 'udp port 47808'

# Read without GUI
tcpdump -r bacnet.pcap -c 5 -n
```

Our helper:

```bash
cd lessons/lab-scripts
PCAP_SECONDS=15 PCAP_IFACE=enp3s0 ./capture_pcap.sh day38-bench "udp port 47808 or tcp port 443"
```

**`-s 0`**: full snaplen—don't truncate BACnet payloads.

**`-n`**: no DNS—show IPs.

### Why This Matters

Commissioning without pcaps is guessing. Techs who can capture once and analyze offline win arguments about routing and firewalls.

### Mini examples

- Capture only host `192.168.204.200`.
- File size sanity: 30s BACnet on quiet net ≈ small MB.

### Micro exercises

1. Run capture script during a Python or rusty Who-Is—did you get packets?
2. What does "promiscuous mode" mean in one sentence?
3. Store pcaps under `lessons/pcaps/` with dated names—practice good hygiene.

### Key takeaway

**tcpdump writes truth**—Wireshark is the microscope.

### Wireshark Lab

Open your `day38-bench_*.pcap`.

Try display filters in order:

1. `udp or tcp`
2. `udp.port == 47808`
3. `tcp.port == 443`

Paste filter results count into lab notes (View → Packet List applies filter).
""",
39: """## Day 39 – Wireshark: BACnet on UDP

### Goal

Read **BVLC → NPDU → APDU** layers in Wireshark for a real **ReadProperty** or **Who-Is** capture.

### Concept

Display filter cheat sheet (see [wireshark_filters.md](./lab-scripts/wireshark_filters.md)):

```
udp.port == 47808
bacnet
bacnet.type == 0x10   # Who-Is (example; verify in your capture)
```

Packet details tree:

- **Ethernet / IP / UDP**
- **BACnet Virtual Link Control (BVLC)**
- **Network Layer (NPDU)**
- **Application Layer (APDU)**

### Why This Matters

When rusty-bacnet returns an error, the pcap tells you if the problem is **network** (no reply) or **application** (Error PDU).

### Mini examples

- Identify source/dest IP and UDP ports on one BACnet packet.
- Export one packet as hex and compare to Rust `&[u8]` buffer mindset.

### Micro exercises

1. Capture during `Who-Is`—find **I-Am** in the list.
2. Apply filter `bacnet && ip.addr == 192.168.204.200` (adjust IP).
3. Screenshot one ReadProperty decode for your portfolio.

### Key takeaway

**Filter `udp.port == 47808` first**, then narrow with `bacnet.*` fields.

### Wireshark Lab

```bash
./capture_pcap.sh day39-bacnet "udp port 47808 and host 192.168.204.200"
```

While capturing, trigger a BACnet read from any tool you have.

In Wireshark: **`udp.port == 47808 && bacnet`**
""",
40: """## Day 40 – Wireshark: TCP, TLS & HTTP (Haystack Preview)

### Goal

See how **Haystack HTTPS** looks in Wireshark—TLS handshake, encrypted application data, and why you need **Follow TLS Stream** or proxy logging for JSON bodies.

### Concept

Display filters:

```
tcp.port == 443
tls.handshake.type == 1          # Client Hello
http                             # only if decrypted or HTTP cleartext lab
```

On Niagara self-signed certs, Rust clients often set **`tls_verify = false`** in lab—production uses proper trust stores.

Haystack ops (conceptual):

- `GET /haystack/about`
- `POST /haystack/read` with `text/zinc` body

### Why This Matters

rusty-haystack failures are often **TLS** or **auth**, visible as TCP resets or HTTP 401 before you ever parse Zinc.

### Mini examples

- Count TLS Client Hello vs Server Hello in a short capture to `192.168.204.11`.
- Note: application JSON/Zinc is **inside** TLS—you won't read tag values from encrypted pcaps without keys.

### Micro exercises

1. Capture `curl -vk https://192.168.204.11/haystack/about` (lab credentials).
2. Apply `tcp.port == 443 && ip.addr == 192.168.204.11`.
3. Write why BACnet point values are easier to spot in pcaps than Haystack point values.

### Key takeaway

**TCP reliability first, TLS privacy second**—log at the client when you need Haystack payloads.

### Wireshark Lab

```bash
./capture_pcap.sh day40-haystack-tls "tcp port 443 and host 192.168.204.11"
```

Filters to try:

1. `tcp.port == 443`
2. `tls.handshake.type == 1`
3. (If available) **Analyze → Follow → TCP Stream** for handshake bytes only

### Week 5 capstone

Document your bench: BACnet UDP path + Haystack TCP path + one screenshot each.
""",
}

LESSONS.update({
41: """## Day 41 – Intro rusty-bacnet & Clone the Stack

### Goal

Clone **[rusty-bacnet](https://github.com/jscott3201/rusty-bacnet)**, build examples, and locate **Who-Is / I-Am** and **ReadProperty** entry points in the crate docs.

### Concept

```bash
git clone https://github.com/jscott3201/rusty-bacnet.git
cd rusty-bacnet
cargo build
cargo test --no-run   # compile tests
```

Mental model:

- **BACnet/IP** = UDP `:47808`
- **BVLC** wraps network messages
- rusty-bacnet exposes Rust APIs instead of BACpypes3 objects

Map from Python days: `BAC0.read()` → rusty-bacnet read helpers (exact fn names vary by version—read `examples/`).

### Why This Matters

Open-FDD and edge gateways are moving to **Rust BACnet drivers** for memory safety and predictable latency on Pi-class hardware.

### Mini examples

- List files under `examples/` or `crates/` in your clone.
- Run one example against your lab device `5007 @ 192.168.204.200` if documented.

### Micro exercises

1. Document your `RUSTBACNET_*` or bind IP env vars if the stack needs them.
2. Compare Python Who-Is time vs Rust compile+run time (qualitative is fine).
3. Find where `47808` appears in source (`rg 47808`).

### Key takeaway

**rusty-bacnet is a specialty UDP client/server**—Days 36–39 networking labs are prerequisite, not optional.

### Wireshark Lab

Before running examples:

```bash
./capture_pcap.sh day41-rusty-whois "udp port 47808"
```

Filter: **`udp.port == 47808 && bacnet`**
""",
42: """## Day 42 – ReadProperty in Rust (Device 5007)

### Goal

Issue a **ReadProperty** for `present-value` on an analog object using rusty-bacnet (or a thin wrapper binary you write).

### Concept

Target (adjust to your commission CSV):

- Device ID: **5007**
- Network: `192.168.204.200`
- Example object: `analogInput:1` present-value

Pseudocode shape:

```rust
// Follow your clone's API — names differ by version
// let client = BacnetClient::bind("0.0.0.0:47808")?;
// let pv = client.read_property(device, object, PropertyIdentifier::PresentValue).await?;
// println!("pv = {pv:?}");
```

Log **`Result`** errors—timeouts look different from **Error** PDUs in pcaps.

### Why This Matters

This is the Rust equivalent of your Day 1–10 Python reads—same field skill, new toolchain.

### Mini examples

- Read `object-name` and `present-value` for the same object.
- Print raw enum for **units** if available.

### Micro exercises

1. Capture pcap during read—match Wireshark decode to printed value.
2. Handle timeout with a friendly message (no panic).
3. Write lab notes: object id string you used.

### Key takeaway

**One successful ReadProperty in Rust** proves the whole toolchain: Cargo, UDP, BACnet, bench routing.

### Wireshark Lab

Filter: **`bacnet && ip.addr == 192.168.204.200`**

Find **Complex-ACK** vs **Error** APDU in the tree.
""",
43: """## Day 43 – ReadPropertyMultiple & Polling Loops

### Goal

Batch reads with **RPM**-style APIs and structure a **poll loop** suitable for edge historians.

### Concept

Python RPM lessons used CSV rotation—Rust pattern:

```rust
loop {
    // read multiple objects in one request
    // sleep(Duration::from_secs(60));
}
```

Use **`tokio::time::sleep`** if examples are async; **`thread::sleep`** for sync labs.

Design a `Vec<BacnetPoint>` from Day 32 and iterate.

### Why This Matters

Open-FDD **commission CSVs** become point lists—RPM reduces LAN chatter vs naive one-read-per-point Python loops.

### Mini examples

- Poll 3 points for 3 iterations; log timestamp with `chrono` if in examples.
- Stop loop on Ctrl+C (`ctrlc` crate optional).

### Micro exercises

1. Estimate BACnet traffic: 10 points × RPM vs 10 ReadProperty calls.
2. Store last values in `HashMap<String, f64>`.
3. Capture 60s pcap during poll—count UDP packets.

### Key takeaway

**Batch at the protocol level**—network programming *and* BACnet smarts.

### Wireshark Lab

```bash
PCAP_SECONDS=60 ./capture_pcap.sh day43-rpm "udp port 47808 and host 192.168.204.200"
```

Filter: **`udp.port == 47808`** — use **Statistics → IO Graph** for packet rate.
""",
44: """## Day 44 – WriteProperty & Priority Array (Careful Lab)

### Goal

Understand **WriteProperty** and **priority** in rusty-bacnet—**lab/simulator only** unless you have permission on live equipment.

### Concept

BACnet writes target a **priority level** (1–16). Releasing to schedule often means writing **NULL** at priority 8 (vendor patterns vary—verify on your device doc).

```rust
// NEVER run against production without change control
// client.write_property(..., priority: 8, value: ...)?;
```

Always read back **priority-array** and **present-value** after a test write.

### Why This Matters

Rust makes it easy to ship powerful tools—**discipline** matters more than language.

### Mini examples

- Document your site policy: who approves writes?
- Read priority array without writing anything.

### Micro exercises

1. Explain difference between **present-value** and priority 8 slot in prose.
2. PCAP: can you see WriteProperty in Wireshark? (filter `bacnet`)
3. If no write-safe point exists, simulate with a local BACnet simulator instead.

### Key takeaway

**Read-only mastery first.** Writes in Rust are the same responsibility as writes in Python or Workbench.

### Wireshark Lab

If using simulator write test:

Filter: **`bacnet.type == 0x0f`** (confirm type in your Wireshark version for WriteProperty).
""",
45: """## Day 45 – Who-Is / I-Am Device Discovery Scan

### Goal

Build or run a **discovery scan** listing device IDs and addresses—Rust replacement for Python Who-Is apps.

### Concept

Discovery flow:

1. Send **Who-Is** (global or range)
2. Collect **I-Am** responses into `HashMap<u32, SocketAddr>`
3. Print table sorted by device id

```rust
// for (id, addr) in devices.iter() {
//     println!("{id} @ {addr}");
// }
```

### Why This Matters

Commissioning starts with **what's on the wire**—same as vibe_code_apps discovery checkpoints.

### Mini examples

- Limit scan to device range `5000-5010`.
- Compare scan results to your known `5007` bench device.

### Micro exercises

1. Run scan while capturing pcap—count I-Am packets.
2. Export device list to CSV from Rust (`writeln!` is enough).
3. Merge duplicate I-Ams—why might you see two?

### Key takeaway

**Discovery is UDP broadcast/multicast behavior**—routing issues show up here first.

### Wireshark Lab

Filter: **`bacnet && bacnet.bvlc.function == 0x0b`** (Who-Is / I-Am family—verify field names in your Wireshark build).
""",
46: """## Day 46 – BACnet Capstone: Mini Commission Tool

### Goal

Combine discovery + RPM + CSV log in one **`cargo` binary**—your Rust BACnet portfolio piece.

### Concept

Deliverable spec:

- Subcommand or flags: `discover`, `poll`
- Output: `commission_snapshot.csv` with columns `device,object,pv,timestamp`
- Graceful errors; no unwrap on network paths

### Why This Matters

This mirrors **open-fdd** commissioning flows—Rust is how the edge crate implements them under the hood.

### Mini examples

- Add `--device 5007` filter flag.
- Log to stderr, data to stdout (Unix tool hygiene).

### Micro exercises

1. Run 5-minute poll; graph packet rate from pcap.
2. Peer review: can a tech run your binary with `--help` only?
3. Link to your vibe_code_apps Python equivalent—what improved?

### Key takeaway

**Small, reliable CLI tools** win in the field—Rust + Cargo + clap (optional) is a strong combo.

### Wireshark Lab

Full bench capture during capstone:

```bash
./capture_pcap.sh day46-capstone "udp port 47808 or tcp port 443"
```

Filters: BACnet **`udp.port == 47808`**, Haystack **`tcp.port == 443`** — same file, two stories.
""",
47: """## Day 47 – Async Rust Preview (tokio & BACnet)

### Goal

See why rusty-bacnet examples often use **`async`/`await`** and **`tokio`**—without becoming an async expert yet.

### Concept

```rust
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // let reply = client.read(...).await?;
    Ok(())
}
```

**async** lets one thread wait on many UDP/HTTP operations—useful on gateways polling BACnet + Haystack + Modbus.

Sync vs async rule of thumb:

- Sync: fine for labs and single-device tools
- Async: edge services with many concurrent I/O tasks

### Why This Matters

Open-FDD bridge services multiplex drivers—async runtime is structural, not trendy.

### Mini examples

- Add `.await` to one example; read compiler errors if you forget `async fn`.
- Compare `thread::sleep` blocking vs `tokio::time::sleep` in async context.

### Micro exercises

1. When would blocking UDP recv freeze an async service?
2. Run `cargo tree | head`—spot `tokio` in dependency graph.
3. One paragraph: Python asyncio vs Rust tokio similarities.

### Key takeaway

**Learn sync sockets first (Days 36–37), async second**—same order as many networking courses, then production stacks.
""",
48: """## Day 48 – HTTP Mental Model for Haystack

### Goal

Map **HTTP methods, status codes, and headers** to Haystack REST ops before touching rusty-haystack.

### Concept

| Haystack op | HTTP | Body |
|-------------|------|------|
| about | GET `/haystack/about` | — |
| read | POST `/haystack/read` | Zinc filter |
| ops | GET `/haystack/ops` | — |

Status codes you'll meet:

- **200** OK
- **401** Unauthorized (wrong auth scheme)
- **404** wrong path
- **415** wrong content type

```bash
curl -sk -u 'user:pass' https://192.168.204.11/haystack/about
```

### Why This Matters

Haystack is **not BACnet**—it's web protocol on TCP. rusty-haystack is an HTTP client with Zinc parsing.

### Mini examples

- List response headers from `/about`—find `Content-Type`.
- Compare HTTP/1.1 vs HTTP/2 in Wireshark (optional).

### Micro exercises

1. What port? What transport? (Day 35 review)
2. Why POST for read—not GET?
3. Capture curl with tcpdump; filter `tcp.port == 443`.

### Key takeaway

**REST = HTTP semantics + resource paths**—Project Haystack defines the ops, Niagara implements nHaystack.

### Wireshark Lab

Filter: **`tcp.port == 443 && ip.addr == 192.168.204.11`**
""",
49: """## Day 49 – rusty-haystack Client Setup

### Goal

Clone **[rusty-haystack](https://github.com/jscott3201/rusty-haystack)**, build **`haystack-client`**, and run the Niagara demo if present.

### Concept

```bash
git clone https://github.com/jscott3201/rusty-haystack.git
cd rusty-haystack
cargo build -p haystack-client
# demo path may vary:
cargo run -p niagara-read -- --help
```

Config knobs (lab):

- Base URL: `https://192.168.204.11/haystack`
- Auth: **HTTP Basic** on many Niagara stations (not always SCRAM)
- TLS: `tls_verify = false` for self-signed lab certs only

See also: `vibe_code_apps_17/nhaystack-niagara-pi-tutorial/`

### Why This Matters

Same building, two protocols: **UDP BACnet** for OT points, **HTTPS Haystack** for semantic tags and ops.

### Mini examples

- Print `/about` server name and Haystack version string.
- Compare response time to a BACnet ReadProperty (qualitative).

### Micro exercises

1. Document which auth mode your station uses (Basic vs SCRAM probe).
2. Build with `--release` before timing.
3. Read `ClientConfig` or equivalent in source.

### Key takeaway

**rusty-haystack sits in the TCP/HTTP layer** of your curriculum—after Days 37–40, before RDF weeks.

### Wireshark Lab

During `about` fetch:

```bash
./capture_pcap.sh day49-haystack-about "tcp port 443 and host 192.168.204.11"
```
""",
50: """## Day 50 – Haystack /read & Zinc Filters

### Goal

Execute a **read** op with a Zinc filter (e.g. `point and temp`) and parse rows in Rust or log raw Zinc.

### Concept

Example filter ideas:

```
point and temp
siteRef == @yourSite
equipRef == @ahu1
```

Zinc response is **text grid**—columns like `id`, `curVal`, `unit`.

In rusty-haystack, follow crate examples for `read()` returning typed rows or strings.

### Why This Matters

FDD rules want **curVal** time series—Haystack read is how Niagara exposes normalized tags without BACnet object numbers.

### Mini examples

- Read one known OA-T tag from your golden fixtures.
- Limit columns if API supports projection.

### Micro exercises

1. Save Zinc body to `read_response.zinc` file from client debug logging.
2. Match one `curVal` to a BACnet present-value for same point (if mapped).
3. PCAP note: payload encrypted—trust client logs for body content.

### Key takeaway

**Zinc is the on-the-wire data language** for Haystack reads—RDF/Turtle comes later as a modeling view.

### Wireshark Lab

Encrypted traffic—practice **client-side logging** instead of display filters for body. Filter handshake only: **`tls.handshake`**
""",
51: """## Day 51 – Auth: HTTP Basic vs Haystack SCRAM

### Goal

Understand why **Niagara nHaystack** often needs **Basic auth**, while upstream rusty-haystack defaults may probe **SCRAM**—and how to configure each.

### Concept

**HTTP Basic**: `Authorization: Basic base64(user:pass)` every request—simple, common on N4 stations with `HTTPBasicScheme`.

**Haystack SCRAM**: challenge/response (`HELLO` → `SCRAM` → `BEARER` token)—Project Haystack spec; not always enabled on vendors.

Lab script reference:

```bash
vibe_code_apps_17/nhaystack-niagara-pi-tutorial/scripts/04_probe_scram_vs_basic.sh
```

Rust config pattern:

```rust
// AuthMode::Basic { username, password }
// vs AuthMode::Scram — see haystack-client config in rusty-haystack fork demos
```

### Why This Matters

Most "rusty-haystack doesn't work on Niagara" reports are **auth + TLS**, not Rust bugs.

### Mini examples

- Intentionally wrong password—confirm **401** in logs and pcap (TLS outer layer only).
- Successful Basic read after fixing creds.

### Micro exercises

1. Run SCRAM probe script—paste one-line result (pass/fail).
2. Document Workbench scheme name for your user.
3. When is Basic acceptable on a LAN lab vs production?

### Key takeaway

**Match auth to server capability**—read `/about` unauthenticated is rare; read ops need the scheme the station exposes.

### Wireshark Lab

You won't see passwords in pcaps (TLS). Verify **TCP connection completes**: **`tcp.port == 443`**
""",
52: """## Day 52 – Golden Fixtures & Offline Haystack Dev

### Goal

Use **golden HTTP fixtures** from the niagara tutorial to develop rusty-haystack parsers without hammering live Niagara.

### Concept

Path: `vibe_code_apps_17/nhaystack-niagara-pi-tutorial/fixtures/`

Capture script:

```bash
scripts/03_capture_golden_fixtures.sh
```

Develop pattern:

1. Record real responses once (with permission)
2. Commit redacted **golden** files
3. Unit test client against fixtures (local `mockito` or file:// server—stretch)

### Why This Matters

Network programming best practice: **separate protocol parsing from live I/O** so CI runs without your bench VLAN.

### Mini examples

- Diff `about.zinc` golden vs live `/about`.
- List ops available in fixture metadata.

### Micro exercises

1. Capture golden set on your N4.15 station if not present.
2. Write one test that loads fixture string and asserts row count > 0.
3. Explain replay value when 192.168.204.11 is offline.

### Key takeaway

**Fixtures are how Rust projects test HTTP clients** without always-on Niagara hardware.

### Wireshark Lab

Optional: capture during golden capture script run—filter **`tcp.port == 443`**
""",
53: """## Day 53 – Correlate Haystack Tags with BACnet Points

### Goal

Build a **mapping table** (CSV or Rust struct) linking Haystack `id` ↔ BACnet `device:object` for one AHU on your bench.

### Concept

```rust
struct PointMap {
    haystack_id: String,
    bacnet_device: u32,
    object_type: u16,
    instance: u32,
}
```

Workflow:

1. Haystack read → list temp points for equip
2. BACnet RPM → list analog inputs
3. Human or rules-assisted alignment (name patterns)

Open-FDD uses commission CSVs—same idea.

### Why This Matters

Multi-protocol gateways need **one logical point identity**—RDF weeks formalize this; today you do it in a table.

### Mini examples

- Map OA-T Haystack tag to BACnet AI if both exist.
- Note unmapped points—document why.

### Micro exercises

1. Five-row CSV `haystack_id,bacnet_obj,pv_haystack,pv_bacnet,delta`.
2. If deltas differ, hypothesis: stale cache vs unit mismatch.
3. Dual capture: BACnet UDP + Haystack HTTPS same minute.

### Key takeaway

**Interoperability is mapping**, not magic—Rust holds the table; RDF will name relationships properly.

### Wireshark Lab

```bash
./capture_pcap.sh day53-dual "udp port 47808 or (tcp port 443 and host 192.168.204.11)"
```

Filters separately: **`udp.port == 47808`** and **`tcp.port == 443`**
""",
54: """## Day 54 – Haystack Capstone: niagara-read Tool

### Goal

Ship a polished **`niagara-read`** (or your fork) with clap flags: URL, auth mode, filter, output format.

### Concept

Reference: `rusty-haystack/demo/niagara_sample/niagara-rusty-scrape/`

Flags to support:

- `--url`, `--user`, `--pass`
- `--auth basic|scram`
- `--filter 'point and temp'`
- `--probe-scram` diagnostic

### Why This Matters

This is the Rust/network capstone before RDF—HTTP + TLS + auth + parsing in one binary.

### Mini examples

- JSON lines output for agent consumption (optional).
- Exit code non-zero on auth failure.

### Micro exercises

1. README with example command for your bench.
2. Run tool in loop 10×—memory stable? (qualitative)
3. Add to vibe_code_apps_17 tutorial index.

### Key takeaway

**Field-ready Haystack CLI in Rust**—network course outcome alongside BACnet capstone.

### Wireshark Lab

One final Haystack capture during demo for portfolio zip.
""",
55: """## Day 55 – From Network Bytes to Graphs: Why RDF?

### Goal

After protocols, step back: **triples** model relationships BACnet object numbers and Haystack tags can't merge alone.

### Concept

A **triple**: `(subject, predicate, object)`

Example intent:

```
ex:AHU1  brick:hasPoint  ex:OA-T .
ex:OA-T  rdf:type        brick:Outside_Air_Temperature_Sensor .
```

Rust preview:

```rust
type Triple = (String, String, String);
let mut graph: Vec<Triple> = Vec::new();
graph.push(("ex:AHU1".into(), "brick:hasPoint".into(), "ex:OA-T".into()));
```

No `rdflib`—we stay in **Rust data structures** through Day 75.

### Why This Matters

Brick / Haystack / **ASHRAE 223P** interoperability targets **graphs**, not CSV columns alone.

### Mini examples

- Draw three circles: BACnet, Haystack, RDF—arrows for "maps to".
- List 3 predicates you'd want between AHU and VAV.

### Micro exercises

1. Convert your Day 53 mapping row into two triples.
2. Why global IRIs beat bare strings `"OA-T"`?
3. Read Haystack **RDF** export docs (vendor)—does Niagara emit RDF? (often tags/Zinc first)

### Key takeaway

**RDF is the semester cap after networking**—Rust implements graphs with structs, not Python rdflib.

### Wireshark Lab

Rest day—or re-open Day 46 capstone pcap for protocol portfolio review.
""",
})

from _rdf_days import LESSONS_RDF
LESSONS.update(LESSONS_RDF)

def main():
    base = Path(__file__).parent
    for day, content in sorted(LESSONS.items()):
        if day < 28 or day > 75:
            continue
        path = base / f"day{day:02d}.md"
        path.write_text(content.strip() + "\n", encoding="utf-8")
        print(f"wrote {path.name}")
    print(f"Total: {len([d for d in LESSONS if 28 <= d <= 75])} lessons")

if __name__ == "__main__":
    main()
