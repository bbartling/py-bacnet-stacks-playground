## Day 51 – Auth: HTTP Basic vs Haystack SCRAM

### Goal

Understand why **Niagara nHaystack** often needs **Basic auth**, while upstream rusty-haystack defaults may probe **SCRAM**—and how to configure each.

### Concept

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

### Why This Matters

Most "rusty-haystack doesn't work on Niagara" reports are **auth + TLS**, not Rust bugs.

### Mini examples

- Intentionally wrong password—confirm **401** in logs and pcap (TLS outer layer only).
- Successful Basic read after fixing creds.

### Micro exercises

1. Run SCRAM probe script—paste one-line result (pass/fail).
2. Document Workbench scheme name for your user.
3. When is Basic acceptable on a LAN lab vs production?

### Key takeaway

**Match auth to server capability**—read `/about` unauthenticated is rare; read ops need the scheme the station exposes.

### Wireshark Lab

You won't see passwords in pcaps (TLS). Verify **TCP connection completes**: **`tcp.port == 443`**
