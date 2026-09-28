# pyhaystack client probe

This read-only probe uses pyhaystack for Zinc grids and history values. Because
pyhaystack's Niagara 4 session expects Niagara's proprietary browser-login
endpoints, `client.py` obtains a standard Haystack bearer token through the
fixture helper and injects it into a deliberately small pyhaystack session.

The probe covers:

- discovery with `read("point and his")`;
- a single-sensor `hisRead`; and
- bulk backfill semantics by discovering every historized point and reading the
  same calendar range for each. pyhaystack performs this as one `hisRead` per
  point; it does not issue the Project Haystack multi-point batch grid.

```sh
python -m venv .venv-pyhaystack
.venv-pyhaystack/bin/pip install \
  'git+https://github.com/ChristianTremblay/pyhaystack.git'

.venv-pyhaystack/bin/python clients/pyhaystack/client.py \
  --url http://192.168.204.12:8080/api --mode single

.venv-pyhaystack/bin/python clients/pyhaystack/client.py \
  --url http://192.168.204.12:8080/api --mode bulk
```

The bulk probe expects four points and 384 quarter-hour values on an ordinary
Chicago day. SQL persistence remains the responsibility of the fixture's
idempotent SQLite backfill client or the future Postgres collector.
