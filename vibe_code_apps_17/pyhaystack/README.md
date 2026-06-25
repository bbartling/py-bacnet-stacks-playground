# pyhaystack playground

Local scratch space for [**pyhaystack**](https://github.com/ChristianTremblay/pyhaystack) — a Python client for Haystack servers including Niagara 4/AX (nHaystack), SkySpark, and WideSky.

Upstream repo: [https://github.com/ChristianTremblay/pyhaystack](https://github.com/ChristianTremblay/pyhaystack)

Docs: [Connecting to a haystack server](https://pyhaystack.readthedocs.io/en/latest/connect.html)

## Setup

```bash
cd vibe_code_apps_17/pyhaystack
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp env.example .env
# edit .env with your Niagara credentials
```

Requires **hszinc 1.3+** (pulled in via `requirements.txt`).

## Smoke test — Niagara 4 (nHaystack)

After [nhaystack-niagara-pi-tutorial](../nhaystack-niagara-pi-tutorial/) proves Basic auth and `/haystack/about` work, try pyhaystack against the same station:

```python
import logging
import os

import pyhaystack

logging.basicConfig(level=logging.INFO)

uri = os.environ["HAYSTACK_URI"]          # e.g. https://192.168.204.11
username = os.environ["HAYSTACK_USER"]
password = os.environ["HAYSTACK_PASS"]

session = pyhaystack.connect(
    implementation="n4",
    uri=uri,
    username=username,
    password=password,
    http_args={
        "tls_verify": False,              # lab self-signed cert
        "insecure_requests_warning": False,
    },
)

# Lazy connect — first request logs in
about = session.about()
print(about)
```

Load env vars before running:

```bash
source .env
python smoke_about.py   # add scripts here as you experiment
```

## Niagara auth notes

- Service accounts often need **HTTP Basic** on `UserService` (see nhaystack tutorial).
- pyhaystack may use digest by default on some Niagara versions; pass `http_args={"debug": True}` and enable `logging.DEBUG` if auth fails ([issue #67](https://github.com/ChristianTremblay/pyhaystack/issues/67)).

## Option — clone upstream for hacking

```bash
git clone https://github.com/ChristianTremblay/pyhaystack.git upstream
cd upstream
pip install -e .
```

The `upstream/` directory is gitignored.

## Next steps in this folder

- `read` filters matching the Rust smoke test (`point and cur`)
- History reads + pandas export for FDD workflows
- Compare behavior with [rusty-haystack](../rusty-haystack/) on the same tags and filters
