# rusty-haystack playground

Local scratch space for experimenting with [**rusty-haystack**](https://github.com/jscott3201/rusty-haystack) — a high-performance Rust implementation of Project Haystack with HTTP client/server, CLI, and PyO3 Python bindings (`import rusty_haystack`).

Upstream repo: [https://github.com/jscott3201/rusty-haystack](https://github.com/jscott3201/rusty-haystack)

## Prerequisites

- Rust 1.93+ (edition 2024)
- `cargo`

For Python bindings: [maturin](https://www.maturin.rs/) and a Python 3.10+ venv.

## Option A — clone upstream here (local only)

```bash
cd vibe_code_apps_17/rusty-haystack
git clone https://github.com/jscott3201/rusty-haystack.git upstream
cd upstream
cargo build --workspace --exclude rusty-haystack
cargo test --workspace --exclude rusty-haystack
```

The `upstream/` directory is gitignored — keep the clone local or add a submodule later if you want it tracked.

## Option B — use upstream from anywhere

```bash
git clone https://github.com/jscott3201/rusty-haystack.git ~/src/rusty-haystack
cd ~/src/rusty-haystack
cargo run -p rusty-haystack-cli -- serve --demo --port 8080
```

Then query the demo server:

```bash
curl http://localhost:8080/api/about
```

## Demo server (from upstream)

```bash
cargo run -p rusty-haystack-cli -- serve --demo --port 8080
# bind all interfaces: add --host 0.0.0.0
```

Set CLI password via `HAYSTACK_PASSWORD` (see upstream [docs/configuration.md](https://github.com/jscott3201/rusty-haystack/blob/main/docs/configuration.md)).

## Connecting to Niagara nHaystack

After the [nhaystack-niagara-pi-tutorial](../nhaystack-niagara-pi-tutorial/) smoke tests pass, try rusty-haystack’s HTTP client against the same station base URL (HTTPS, HTTP Basic auth). SCRAM auth applies to rusty-haystack servers; Niagara nHaystack typically uses Basic — use the client transport options documented in upstream [docs/client.md](https://github.com/jscott3201/rusty-haystack/blob/main/docs/client.md).

## Next steps in this folder

- Add small Rust binaries or scripts that call `haystack-client` against your lab station
- Build/install the PyO3 module and compare with [pyhaystack](../pyhaystack/) on the same `/read` filters
- Benchmark Zinc encode/decode vs raw `curl` CSV (see upstream [Benchmarks.md](https://github.com/jscott3201/rusty-haystack/blob/main/Benchmarks.md))
