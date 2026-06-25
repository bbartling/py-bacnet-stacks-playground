# Quick copy/paste commands

## 1. Unzip

```bash
unzip nhaystack-niagara-pi-tutorial.zip
cd nhaystack-niagara-pi-tutorial
```

## 2. Configure

```bash
cp env.example .env
nano .env
```

Set:

```bash
export JACE_HOST="192.168.204.11"
export HAYSTACK_USER="open_fdd"
export HAYSTACK_PASS="your-real-password"
export HAYSTACK_BASE="https://${JACE_HOST}/haystack"
```

## 3. Run bash smoke test

```bash
chmod +x scripts/*.sh
./scripts/01_bash_smoke_test.sh
```

## 4. Run Rust smoke test

```bash
./scripts/install_pi_deps.sh
./scripts/02_run_rust_smoke.sh
```

## 5. Or run manually

```bash
source .env
cargo run
```
