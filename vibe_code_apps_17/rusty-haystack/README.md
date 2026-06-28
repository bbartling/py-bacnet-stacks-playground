# rusty-haystack playground

Local scratch space for [**rusty-haystack**](https://github.com/jscott3201/rusty-haystack) — Project Haystack in Rust (codecs, client, server, CLI, PyO3).

For **Niagara nHaystack**, use the **[bbartling fork](https://github.com/bbartling/rusty-haystack)** with:

- `AuthMode::Basic` — HTTP Basic (Niagara `HTTPBasicScheme`)
- `ClientConfig::niagara_lab()` — `tls_verify: false` for self-signed station cert
- Demo: `demo/niagara_sample/niagara-rusty-scrape` (`cargo run -p niagara-read`)

Upstream [jscott3201/rusty-haystack](https://github.com/jscott3201/rusty-haystack) implements **SCRAM** for SkySpark and `haystack-server` — not Niagara nHaystack 3.3.

## After nhaystack-niagara-pi-tutorial passes

```bash
# From tutorial (uses fork checkout):
export RUSTY_HAYSTACK_ROOT=~/rusty-haystack
cd ../nhaystack-niagara-pi-tutorial
source .env
./scripts/05_rusty_haystack_niagara_read.sh
```

Or clone the fork:

```bash
git clone https://github.com/bbartling/rusty-haystack.git ~/rusty-haystack
cd ~/rusty-haystack/demo/niagara_sample/niagara-rusty-scrape
cp env.example .env && source .env
cargo run -p niagara-read -- --auth basic --probe-scram
```

## Demo server (SCRAM — not Niagara)

```bash
cargo run -p rusty-haystack-cli -- serve --demo --port 18080
curl http://127.0.0.1:18080/api/about   # expect WWW-Authenticate: HELLO
```

Use a free port if `:8080` is taken (e.g. Open-FDD bridge).

## Option A — clone upstream here (local only)

```bash
git clone https://github.com/jscott3201/rusty-haystack.git upstream
cd upstream && cargo build --workspace --exclude rusty-haystack
```

The `upstream/` directory is gitignored.

## Next steps

- Compare Zinc decode vs tutorial CSV in [nhaystack-niagara-pi-tutorial](../nhaystack-niagara-pi-tutorial/)
- Feed golden fixtures into a future nHaystack fixture server ([FIXTURES_AND_SIM.md](../nhaystack-niagara-pi-tutorial/FIXTURES_AND_SIM.md))
