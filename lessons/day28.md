## Day 28 – Install Rust & Cargo (Your First Binary)

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
