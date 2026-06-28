# Quick copy/paste commands

## 1. Configure

```bash
cd nhaystack-niagara-pi-tutorial
cp env.example .env
nano .env
chmod +x scripts/*.sh
```

Set `HAYSTACK_PASS` to the Niagara `open_fdd` password (Workbench → HTTPBasicScheme).

## 2. Bash smoke test

```bash
./scripts/01_bash_smoke_test.sh
```

## 3. Rust smoke test

```bash
./scripts/install_pi_deps.sh   # Pi only
./scripts/02_run_rust_smoke.sh
# or:
cargo run -- --probe-scram
```

## 4. Golden fixtures (do while N4.15 station is live)

```bash
./scripts/03_capture_golden_fixtures.sh
ls -la fixtures/golden/
```

## 5. SCRAM vs Basic probe

```bash
./scripts/04_probe_scram_vs_basic.sh
```

## 6. rusty-haystack (optional fork)

```bash
git clone https://github.com/bbartling/rusty-haystack.git ~/rusty-haystack
export RUSTY_HAYSTACK_ROOT=~/rusty-haystack
./scripts/05_rusty_haystack_niagara_read.sh
```

See [FIXTURES_AND_SIM.md](FIXTURES_AND_SIM.md) for the future nHaystack API double.
