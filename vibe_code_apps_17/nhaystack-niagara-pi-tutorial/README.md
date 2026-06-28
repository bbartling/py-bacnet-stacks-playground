# Niagara nHaystack → Pi / Linux lab tutorial (Niagara 4.15)

Part of **[vibe code app 17](../README.md)** — Project Haystack playground (Niagara lab → golden fixtures → [rusty-haystack](../rusty-haystack/) → [pyhaystack](../pyhaystack/) → Open-FDD).

**Rust course (Days 28–75):** [lessons/day28.md](../../lessons/day28.md) · [capstone bundle](../../lessons/capstone/) · [rust-lessons hub](../rust-lessons/README.md)

This tutorial proves a Linux host (Raspberry Pi or WSL bench) can:

1. Authenticate to **Niagara 4 (N4) 4.15** nHaystack over HTTPS
2. Read live BACnet point values via Haystack `read`
3. Capture **golden fixtures** for a future non-Niagara API sim
4. Compare **HTTP Basic** (Niagara) vs **SCRAM** (SkySpark / rusty-haystack server)

Stack progression:

```text
bash + curl          →  network, auth, nHaystack config
Rust nhaystack-smoke →  programmatic read + SCRAM probe
golden fixtures      →  survive Workbench license expiry
rusty-haystack       →  HaystackClient AuthMode::Basic (fork)
pyhaystack / Open-FDD →  product integration
```

## Observed Niagara 4.15 station (lab)

Captured from `GET /haystack/about` on the Open-FDD bench:

| Field | Value |
|-------|--------|
| **Platform** | **Niagara 4 (N4)** — Tridium |
| **Niagara build** | **4.15.3.28** |
| **Station name** | `v4Fifteen` |
| **nHaystack module** | **3.3.0.0** |
| **Haystack protocol** | **2.0** |
| **HTTPS URL** | `https://192.168.204.11/haystack` |
| **BACnet device** | `BENS-BENCHTEST-BOX` under `Drivers/BacnetNetwork` |
| **API user** | `open_fdd` with **`HTTPBasicScheme`** |

Example points (`read?filter=point and cur`):

| dis | Typical | unit |
|-----|---------|------|
| OA-H | ~51 %RH | %RH |
| OA-T | ~72 °F | °F |
| DUCT-T | ~65–69 °F | °F |
| DUCT-P | ~-0.14 | in/wc |
| STAT ZN-T | ~73 °F | °F |
| ACTUATOR-0 | writable | % |

See [`fixtures/example/about.zinc.example`](fixtures/example/about.zinc.example) for a committed `/about` sample (no secrets).

## HTTP Basic vs SCRAM (read this once)

| | **Niagara nHaystack** | **SkySpark / rusty-haystack server** |
|--|------------------------|--------------------------------------|
| Auth | `Authorization: Basic …` | `HELLO` → `SCRAM` → `BEARER` |
| Workbench | `HTTPBasicScheme` on service user | N/A |
| Client flag | `--auth basic` / curl `-u` | `--auth scram` |

Niagara **`HTTPBasicScheme` is not Haystack SCRAM.** SCRAM HELLO on `/haystack/about` returns `401` HTML with **no** `WWW-Authenticate: SCRAM`.

Verify:

```bash
./scripts/04_probe_scram_vs_basic.sh
cargo run -- --probe-scram
```

## Working topology

```text
Raspberry Pi
  └── curl / Rust client
      └── HTTPS 443
          └── Windows Niagara station
              └── Niagara WebService
                  └── NHaystackService servlet at /haystack
                      └── Niagara station database / BacnetNetwork points
```

Example lab values:

```text
Windows station IP:        192.168.204.11
Niagara WebService port:   443 / HTTPS
Haystack base URL:         https://192.168.204.11/haystack
nHaystack servlet name:    haystack
Niagara version observed:  4.15.3.28
nHaystack module observed: 3.3.0.0
```

## Niagara / Workbench setup summary

### 1. BACnet Network

The BACnet/IP port was bound to the Windows Ethernet adapter:

```text
Adapter/IP: 192.168.204.11
BACnet UDP: 47808 / 0xBAC0
```

For same-subnet BACnet/IP testing, keep routing off:

```text
Ip Port Enabled: true
Routing Enabled: false
Maintain Routing Enabled: false
BBMD Address: null
```

Why:

`Routing Enabled` is only needed when Niagara is intentionally routing between BACnet networks, such as BACnet/IP to MS/TP, or between multiple BACnet network segments. For a simple same-subnet BACnet/IP station, routing can keep the BACnet stack from initializing cleanly.

### 2. nHaystack service

In Workbench:

```text
Config → Services → NHaystackService
```

The servlet should be enabled:

```text
NHaystackService → Servlet
Status: {ok}
Enabled: true
Servlet Name: haystack
```

This makes the Haystack API available at:

```text
https://<station-ip>/haystack
```

For this setup:

```text
https://192.168.204.11/haystack
```

After adding or changing Niagara points/tags, run:

```text
NHaystackService → Actions → Rebuild Cache
```

### 3. Niagara authentication for API access

The first curl tests may fail with either:

```text
401 Unauthorized
```

or:

```text
302 Found → /login
```

That usually means HTTPS and nHaystack are reachable, but the Niagara user is still configured for browser-style Niagara login instead of API-style HTTP Basic authentication.

The fix used in this lab:

```text
Config → Services → AuthenticationService → Authentication Schemes
```

Add an HTTP Basic authentication scheme, then set the `open_fdd` service user to use that scheme:

```text
Config → Services → UserService → open_fdd
Authentication Scheme Name: HTTPBasicScheme
```

Keep the global/default authentication scheme as `DigestScheme`. Only the machine/service account needs HTTP Basic.

Workbench screenshots for this lab:

```text
AuthenticationService → WebServicesSchemes → HTTPBasicScheme (enabled)
UserService → open_fdd → Authentication Scheme Name: HTTPBasicScheme
UserService → open_fdd → Enabled: true, Roles: admin (lab only)
```

## Golden fixtures (capture before license expires)

While the live N4.15 station is up, snapshot responses for offline dev and a future **nHaystack API fixture server**:

```bash
source .env
chmod +x scripts/*.sh
./scripts/03_capture_golden_fixtures.sh
```

Writes to `fixtures/golden/` (gitignored). See [`fixtures/README.md`](fixtures/README.md) and [`FIXTURES_AND_SIM.md`](FIXTURES_AND_SIM.md).

**Roadmap:** static HTTP façade in vibe code app 17 → BACnet-backed sim → `pointWrite` — **not** in upstream rusty-haystack.

## Raspberry Pi environment variables

Copy `env.example` to `.env` and edit it:

```bash
cp env.example .env
nano .env
```

Example:

```bash
export JACE_HOST="192.168.204.11"
export HAYSTACK_USER="open_fdd"
export HAYSTACK_PASS="replace-me"
export HAYSTACK_BASE="https://${JACE_HOST}/haystack"
```

What these mean:

```text
JACE_HOST       The Niagara server IP. In this lab it is the Windows station, not an actual JACE.
HAYSTACK_USER   Niagara service account username.
HAYSTACK_PASS   Niagara service account password. Do not commit this.
HAYSTACK_BASE   Base URL for the nHaystack servlet.
```

## Bash testing

### Option A: run the included script

```bash
cd nhaystack-niagara-pi-tutorial
cp env.example .env
nano .env
chmod +x scripts/*.sh
./scripts/01_bash_smoke_test.sh
```

### Option B: run commands manually

Load your variables:

```bash
source .env
```

Test `/about`:

```bash
curl -k -i -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  "$HAYSTACK_BASE/about"
```

What the flags mean:

```text
-k      Allow Niagara self-signed HTTPS certificate during lab testing.
-i      Include HTTP response headers.
-u      Send HTTP Basic username/password.
```

A good response starts with:

```text
HTTP/1.1 200 OK
```

and returns a Haystack grid like:

```text
ver:"3.0"
productUri,tz,moduleName,serverName,productName,...
```

List supported Haystack operations:

```bash
curl -k -sS -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  -H "Accept: text/zinc" \
  "$HAYSTACK_BASE/ops"
```

What the flags mean:

```text
-sS                 Silent mode but still show errors.
-H "Accept: ..."    Ask nHaystack for a specific response format.
text/zinc           Haystack Zinc grid format.
```

Read all Haystack points as CSV:

```bash
curl -k -sS -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  -H "Accept: text/csv" \
  --get "$HAYSTACK_BASE/read" \
  --data-urlencode "filter=point" | head -50
```

Read current-value points as CSV:

```bash
curl -k -sS -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  -H "Accept: text/csv" \
  --get "$HAYSTACK_BASE/read" \
  --data-urlencode "filter=point and cur" | head -50
```

Save current-value points to a CSV file:

```bash
curl -k -sS -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  -H "Accept: text/csv" \
  --get "$HAYSTACK_BASE/read" \
  --data-urlencode "filter=point and cur" \
  -o nhaystack_points.csv
```

Search for BACnet point paths:

```bash
grep -i "BacnetNetwork\|OA\|DUCT\|STAT\|ACTUATOR" nhaystack_points.csv | head -50
```

## Rust testing

This project includes a Rust smoke client in `src/main.rs`.

It does four things:

```text
1. Calls /haystack/about
2. Calls /haystack/read?filter=point and cur
3. Saves nhaystack_points.csv
4. Parses the CSV and prints only BacnetNetwork point rows
```

### Install basic Pi dependencies

```bash
./scripts/install_pi_deps.sh
```

The Rust project uses `reqwest` with `rustls` and disables default features so OpenSSL is not required by this app.

Important part of `Cargo.toml`:

```toml
reqwest = { version = "0.12", default-features = false, features = ["rustls-tls"] }
```

### Build and run

```bash
source .env
cargo run
# optional SCRAM vs Basic probe:
cargo run -- --probe-scram
```

Or use:

```bash
./scripts/02_run_rust_smoke.sh
```

### rusty-haystack client (fork with AuthMode::Basic)

After smoke tests pass, try the [`bbartling/rusty-haystack`](https://github.com/bbartling/rusty-haystack) fork demo:

```bash
export RUSTY_HAYSTACK_ROOT="$HOME/rusty-haystack"   # clone fork first
./scripts/05_rusty_haystack_niagara_read.sh
```

Uses `niagara-read --auth basic --probe-scram` against the same station URL.

Expected output:

```text
--- /about ---
ver:"3.0"
...

Wrote nhaystack_points.csv

--- BACnet current-value points ---
OA-H               50.8406%RH        %RH      ok       writable= type=control:NumericPoint ...
OA-T               72.4714°F         °F       ok       writable= type=control:NumericPoint ...
DUCT-T             68.8953°F         °F       ok       writable= type=control:NumericPoint ...
DUCT-P             -0.1407in/wc      in/wc    ok       writable= type=control:NumericPoint ...
ACTUATOR-0         55%               %        ok       writable=✓ type=control:NumericWritable ...

Total point/current rows: ...
BACnet point/current rows: ...
```

## Important note about CSV output

The writable Niagara `actions` field can contain embedded newlines. This can make shell output from `curl | head` look strange.

That is still valid CSV.

The Rust example uses the `csv` crate, so it should parse quoted multiline fields correctly.

## Important note about tagging

nHaystack can expose Niagara `ControlPoint` objects as Haystack `point` records even before you manually tag everything.

Without custom semantic tags, you can still get useful raw point inventory:

```text
point
cur
curVal
curStatus
kind
unit
writable
n4SlotPath
axSlotPath
```

But you usually will not get a clean FDD semantic model yet:

```text
site
equip
ahu
vav
equipRef
siteRef
supply air temp sensor
outside air temp sensor
```

Those semantic tags can be added later in Niagara or inferred externally by Open-FDD.

## Troubleshooting

### `curl: Failed to connect ... port 80`

The Pi tried HTTP port 80, but Niagara was listening on HTTPS port 443.

Use:

```bash
export HAYSTACK_BASE="https://192.168.204.11/haystack"
```

### `HTTP/1.1 401 Unauthorized`

The Pi reached Niagara, but username/password or authentication scheme was wrong.

Check:

```text
UserService → open_fdd → Authentication Scheme Name
```

Use HTTP Basic for the API service account.

### `HTTP/1.1 302 Found` with `Location: /login`

Niagara is redirecting the request to browser login.

This usually means the user is still using `DigestScheme` instead of HTTP Basic.

### `HTTP/1.1 404 Not Found`

The WebService is reachable, but the servlet path is wrong or disabled.

Check:

```text
NHaystackService → Servlet → Enabled: true
NHaystackService → Servlet → Servlet Name: haystack
```

### `read?filter=point` returns no useful points

nHaystack is online, but Niagara does not have BACnet points added yet, or the nHaystack cache needs to be rebuilt.

Check:

```text
Drivers → BacnetNetwork → Device Manager
Drivers → BacnetNetwork → Device → Points
NHaystackService → Rebuild Cache
```

### Rust build complains about OpenSSL / `openssl-sys`

This project tries to avoid OpenSSL by using:

```toml
reqwest = { version = "0.12", default-features = false, features = ["rustls-tls"] }
```

Run:

```bash
cargo clean
cargo run
```

If a different dependency still pulls OpenSSL, check it with:

```bash
cargo tree -i openssl-sys
```

A brute-force dev-machine fix is:

```bash
sudo apt update
sudo apt install -y pkg-config libssl-dev ca-certificates
```

But this app should not need that once `reqwest` default features are disabled.

## Next direction

Recommended order:

```text
1. Bash curl           — prove nHaystack reachable (scripts/01)
2. Rust smoke          — read + parse BACnet rows (cargo run)
3. Golden capture      — scripts/03 (before Workbench license ends)
4. SCRAM probe         — scripts/04 + cargo --probe-scram (document Niagara gap)
5. rusty-haystack      — AuthMode::Basic client (scripts/05 or ../rusty-haystack/)
6. pyhaystack          — same station via Python (../pyhaystack/)
7. nHaystack fixture   — FIXTURES_AND_SIM.md (vibe17 or Open-FDD bench profile)
8. Open-FDD            — Haystack driver + MCP (see Open-FDD agent prompts)
```
