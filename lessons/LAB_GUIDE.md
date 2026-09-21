# Rust networking lab guide

[Course index](INDEX.md) · [Wire contracts](WIRE_FORMATS.md) · [Topologies](TOPOLOGIES.md) · [References](SOURCES.md)

## Rust first

The required implementations are Rust. Python companions are **optional**: a small independent client, fixture generator, or result check. You do not need to implement every project twice. Two Rust processes work for most peer exercises; for protocol interoperability, an independent existing stack/tool is preferable to two copies of your own implementation.

If you finished the old Python Day 19, your work still counts. Continue with [Day 20](day20.md) and port your own solution. New learners follow the rewritten Rust-first Days 1–19. There is no archive or requirement to revisit completed fundamentals.

## Workspace and tools

Keep your implementations in a separate learning repository, or under the ignored `lessons/student-work/` directory. Use one small Cargo package per experiment at first; later reuse crates for your codecs and tools. Do not modify working appliance code to make a teaching experiment compile.

From the repository root, a typical start is:

```bash
mkdir -p lessons/student-work
cd lessons/student-work
cargo new day20 --bin
cd day20
cargo run
cargo test
cargo fmt --check
cargo clippy --all-targets -- -D warnings
```

For a standalone complete `rust` block containing `fn main`, save it as `example.rs` in your own workspace and run `rustc --edition 2024 example.rs -o example`, then `./example`. Most snippets deliberately show only a small mechanism. Commands containing `<placeholder>` or an environment variable must be adapted before execution.

Install stable Rust through the [official installation instructions](https://doc.rust-lang.org/book/ch01-01-installation.html). Use edition 2024 for new coursework. Record `rustc -Vv`, `cargo --version`, OS and architecture. Rust edition and compiler version are different settings. Commit Cargo.toml and Cargo.lock for applications. Select current documented crate versions when introducing a dependency; then keep the lockfile fixed while reproducing an experiment. The DIY appliance has its own toolchain and upstream pins: do not silently upgrade them to match the course.

Suggested dependency sequence, not a required giant manifest:

| When | Tools |
| --- | --- |
| 1–25 | Standard library; optional Python standard library |
| 26–28 | clap for CLI, optionally serde for structured reports |
| 29 onward | Linux iproute2, tcpdump, Wireshark or tshark; standard sockets |
| 42 | Maintained capture-container reader; your own selected packet decoders |
| 57 onward | Tokio with only the features needed; tracing; optional bytes |
| 64 onward | Independent Modbus simulator/tool at a recorded version |
| 75 onward | Pinned rusty-bacnet public APIs; optional bacpypes3 external oracle |
| 92 onward | Dedicated Pi OS/network manager and actual supported interfaces |

Linux is the reference lab platform. Windows/macOS can run early Rust work; use a Linux VM for namespaces and Linux router exercises. Do not treat WSL/VM loopback behavior as proof of physical multicast or RS-485 behavior.

## A daily session

1. Read the goal, required subset and acceptance checks. Predict one result on paper.
2. Run the tiny example, then implement the distinct challenge yourself.
3. Test a normal case and the named failure/boundary cases. Add tests where they protect meaningful behavior.
4. Capture only when the exercise involves actual packets. For a codec, exact input bytes and results are sufficient.
5. Write five or six sentences: what you expected, what happened, one surprise, its explanation, and what remains untested.

Ordinary sessions target 45–90 minutes. Hardware and review projects can span evenings. A lesson may be complete as a labeled offline exercise while its physical extension remains pending. Avoid endless prerequisite setup: use fixtures, then return to the live experiment when the equipment is ready.

## Evidence convention

A useful local work folder contains source, README, `evidence/`, and a version record. Keep captures small and do not commit private network payloads, credentials or certificates with private keys. `lessons/student-work/` and generated `lessons/pcaps/` are ignored; deliberately sanitized fixtures are tracked under `fixtures/`.

Every network result should record:

- Program revision, toolchain/dependency versions, OS/kernel and peer implementation.
- Topology, interfaces, link types, addresses, ports and protocol network numbers where applicable.
- Command, time/packet/byte limits, expected result and observed result.
- Capture filter, display filter, frame references and relevant logs.
- Outcome category: **observed**, **fixture-only**, **not run**, or **failed** with an explanation.

A PCAP generated from known bytes is a synthetic fixture, not a successful live network test. A screenshot is useful supporting evidence, but keep the underlying capture when possible. Capture drops, checksum offload, snap length, clock precision and observation point can change what the evidence means.

## Review rubric

Review pages contain a project brief, acceptance criteria and deliverables, without an implementation recipe. Choose your own types, functions and decomposition. Public wire contracts and known-answer fixtures describe interoperability; they do not prescribe the code.

| Area | Ready when |
| --- | --- |
| Behavior | The declared baseline works and unsupported cases are explicit. |
| Failure handling | Named malformed, missing, timeout and boundary cases behave intentionally. |
| Resource limits | Relevant sizes, counts, tasks, queues and deadlines are bounded. |
| Evidence | Inputs, revisions, tests and observations support the claimed outcome. |
| Explanation | You can explain ownership, protocol boundaries and one failure without reading code aloud. |

All applicable baseline criteria should pass before calling a project complete. Record optional/hardware criteria separately. Ask a tutor for a hint or an explanation of the compiler/API before asking for a full implementation. No full course solutions are shipped in the student lesson pages.

## Offline alternatives and hardware boundaries

| Missing capability | Useful fallback | Still unproven |
| --- | --- | --- |
| Second computer | Loopback peer or network namespace | Physical NIC/radio behavior |
| Packet-capture permission | Provided synthetic bytes/PCAP | Live traffic and capture placement |
| BACnet device | Independent simulator or pinned stack fixtures | Real device-specific interoperability |
| IPv6 router | Offline RA/NDP analysis or isolated VM | Actual deployed IPv6 configuration |
| Pi/AP radio | Linux namespace routing plus topology plan | Wi-Fi association, leases after real reboot |
| Serial adapter | PTY and offline serial frames | Electrical/timing behavior |
| Flashable appliance image | Source tests and image study | Exact-image boot/forwarding gates |

Active experiments belong on your isolated lab network. DHCP must stay on the designated lab LAN. Serial passive decode precedes transmitting; one process owns a tty. The shared DIY router bench's current baud/hold rules remain authoritative. A lesson does not authorize altering an occupied building trunk or replacing its software.

## What “all lessons written” means

Every day has authored teaching material and a challenge. It does **not** mean every live lab has been run on your hardware or that student solutions are supplied. See [VALIDATION.md](VALIDATION.md) for the checks performed during this rewrite and remaining learner-run evidence.
