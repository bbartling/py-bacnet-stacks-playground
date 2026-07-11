# Day 51 – Auth: HTTP Basic vs Haystack SCRAM

## Goal

Understand why **Niagara nHaystack** often needs **Basic auth**, while upstream rusty-haystack defaults may probe **SCRAM**—and how to configure each.

## Concept

**HTTP Basic**: `Authorization: Basic base64(user:pass)` every request—simple, common on N4 stations with `HTTPBasicScheme`.

**Haystack SCRAM**: challenge/response (`HELLO` → `SCRAM` → `BEARER` token)—Project Haystack spec; not always enabled on vendors.

Lab script reference:

```bash
vibe_code_apps_17/nhaystack-niagara-pi-tutorial/scripts/04_probe_scram_vs_basic.sh
```

Rust config pattern:

```rust
// AuthMode::Basic { username, password }
// vs AuthMode::Scram — see haystack-client config in rusty-haystack fork demos
```

## Why This Matters

Most "rusty-haystack doesn't work on Niagara" reports are **auth + TLS**, not Rust bugs.

## Mini Examples

- Intentionally wrong password—confirm **401** in logs and pcap (TLS outer layer only).
- Successful Basic read after fixing creds.

## Micro Exercises

1. Run SCRAM probe script—paste one-line result (pass/fail).
2. Document Workbench scheme name for your user.
3. When is Basic acceptable on a LAN lab vs production?

## Wireshark Lab

You won't see passwords in pcaps (TLS). Verify **TCP connection completes**: **`tcp.port == 443`**

## Key Takeaway

**Match auth to server capability**—read `/about` unauthenticated is rare; read ops need the scheme the station exposes.

---

## Python companion — Basic auth header

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
import base64
import requests

user, password = "user", "pass"
token = base64.b64encode(f"{user}:{password}".encode()).decode()
r = requests.get(
    "https://192.168.204.11/haystack/about",
    headers={"Authorization": f"Basic {token}"},
    verify=False,
    timeout=10,
)
print(r.status_code)  # 200 or 401
```

| Rust (main lesson) | Python |
|--------|--------|
| `AuthMode::Basic` / SCRAM | Basic header or `auth=(...)` |
| probe script in tutorial | same 401 vs 200 experiment |
| config in haystack-client | conceptual only |

**Takeaway:** Niagara labs usually need Basic—confirm with a tiny Python GET, then configure rusty-haystack.
