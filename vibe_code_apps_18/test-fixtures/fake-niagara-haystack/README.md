# Fake Niagara 4 / Haystack server

This is a small, deterministic Project Haystack 3.0 simulator for testing an
open FDD pipeline. It behaves like a Niagara nHaystack endpoint for the useful
part of this workflow: discover `point and his` records, call `hisRead` for a
date/range, and load the returned samples into SQLite. It runs on Raspberry Pi
OS with the Python standard library only (Python 3.10+).

It is a test double, not a Niagara replacement. The graph and history are
generated in memory and are regenerated when the process starts. `pointWrite`,
`hisWrite`, watches, and Xeto definitions deliberately return an error grid.

## Run it

```sh
python -m fake_niagara.server --host 0.0.0.0 --port 8080 \
  --username admin --password demo
```

The API root is `http://raspberrypi.local:8080/api`. The default demo account
is `admin` / `demo`; set `FAKE_NIAGARA_PASSWORD` to a different password on a
LAN. The server supports the
Project Haystack SCRAM-SHA-256 handshake (PBKDF2-HMAC-SHA-256) and bearer
headers in the form `Authorization: BEARER authToken=...` used by
`rusty-haystack`. The server implements the standard three-step `HELLO` →
`SCRAM` client-first → `SCRAM` client-final state machine, while also accepting
the two-request legacy form emitted by current `rusty-haystack` releases.
Authentication accepts standards-compliant unpadded
base64url outer values as well as the padded standard-base64 form emitted by
current `rusty-haystack` releases; the inner SCRAM proof remains standard
base64.

For a quick probe, use the included client:

```sh
python -m fake_niagara.client --url http://127.0.0.1:8080/api --discover
python -m fake_niagara.client --point point-ahu1-sat --range yesterday
```

### Client compatibility probes

The older [`pyhaystack`](https://github.com/ChristianTremblay/pyhaystack)
package can parse this fixture's Zinc grids and history. Its built-in
`Niagara4HaystackSession` expects Niagara-specific `/prelogin` and
`/j_security_check` web endpoints rather than standard Haystack HTTP SCRAM, so
the included client supplies a small read-only authentication adapter:

```sh
python -m venv .venv-pyhaystack
.venv-pyhaystack/bin/pip install \
  'git+https://github.com/ChristianTremblay/pyhaystack.git'
.venv-pyhaystack/bin/python clients/pyhaystack/client.py \
  --url http://127.0.0.1:8080/api \
  --username admin --password demo --mode single
.venv-pyhaystack/bin/python clients/pyhaystack/client.py \
  --url http://127.0.0.1:8080/api \
  --username admin --password demo --mode bulk
```

The adapter uses this fixture's standard SCRAM client to obtain a bearer token,
then uses pyhaystack for the read-only `read` and `hisRead` grid operations. It
does not add Niagara's proprietary browser-login surface to the emulator.

The pinned Rust probe is in `clients/rusty-haystack`. It tests both
`HaystackClient::his_read` for one sensor and a real standard multi-point batch
request through `call("hisRead", ...)`. See each client directory's README for
commands and the difference between batch and fan-out behavior.

The sample graph contains one site, two pieces of equipment, and four history
points. Samples are deterministic 15-minute values generated on demand, so a
server that stays up across midnight remains current. The default timezone is
`America/Chicago`, including daylight-saving transitions. Supported history ranges
are `today`, `yesterday`, an ISO date (`2026-09-27`), or an inclusive ISO date
span (`2026-09-25,2026-09-27`). Both a single `hisRead` row and multiple rows
in one batch request are accepted.

## Daily SQLite backfill

Run yesterday's backfill manually:

```sh
python -m fake_niagara.client \
  --url http://raspberrypi.local:8080/api \
  --username admin --password demo \
  --database /var/lib/fake-niagara/history.sqlite3
```

The SQLite table is `haystack_history(point_id, ts, value, value_num,
value_text, value_type, unit, source)` with a primary key on
`(point_id, ts, source)`. Timestamps are normalized to UTC. Rerunning a day
is safe and idempotent, while a corrected value upserts and separate Haystack
sources remain isolated.
Pass `--date YYYY-MM-DD` while experimenting with a specific Chicago calendar day. Batch
`hisRead` uses the Haystack-wide shape: request metadata `range` plus an `id`
row per point; the response has one `ts` column and `v0`, `v1`, ... value
columns whose column metadata carries each point id.
Requests are bounded to 31 days, 10,000 samples, and 32 points per batch;
over-limit requests return Haystack error grids.

## Rust client compatibility

`rusty-haystack`'s HTTP client can connect to this server as follows:

```rust
let client = HaystackClient::connect(
    "http://127.0.0.1:8080/api", "admin", "demo"
).await?;
let grid = client.his_read("@point-ahu1-sat", "yesterday").await?;
```

The server implements GET `about`, `ops`, `formats`, and `libs`; POST
`read`, `readByIds`, `hisRead`, and `close`. Responses default to `text/zinc`.
This test double intentionally supports Zinc only; it does not advertise or
accept JSON. The Zinc codec covers the tags used by the demo, including column
metadata and values with units.

## systemd on Raspberry Pi

Copy the example units and adjust `User`, `WorkingDirectory`, and the install
path if needed:

```sh
sudo install -d /opt/fake-niagara
sudo cp -r fake_niagara /opt/fake-niagara/
sudo install -d -m 700 /etc/fake-niagara
sudo sh -c 'printf "FAKE_NIAGARA_USERNAME=admin\\nFAKE_NIAGARA_PASSWORD=replace-this\\n" > /etc/fake-niagara/fake-niagara.env'
sudo chmod 600 /etc/fake-niagara/fake-niagara.env
sudo cp deploy/fake-niagara.service /etc/systemd/system/
sudo cp deploy/fake-niagara-backfill.service /etc/systemd/system/
sudo cp deploy/fake-niagara-backfill.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fake-niagara.service fake-niagara-backfill.timer
```

The timer runs at 01:15 UTC each day. The backfill service uses the previous
America/Chicago calendar day, matching the fake server's history timezone.

## Tests

```sh
python -m unittest discover -v
```

The integration tests start a real local HTTP server, perform SCRAM, discover
points, read both single and batch history, and verify idempotent SQLite
backfill.
