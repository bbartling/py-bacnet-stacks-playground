## Day 49 – rusty-haystack Client Setup

### Goal

Clone **[rusty-haystack](https://github.com/jscott3201/rusty-haystack)**, build **`haystack-client`**, and run the Niagara demo if present.

### Concept

```bash
git clone https://github.com/jscott3201/rusty-haystack.git
cd rusty-haystack
cargo build -p haystack-client
# demo path may vary:
cargo run -p niagara-read -- --help
```

Config knobs (lab):

- Base URL: `https://192.168.204.11/haystack`
- Auth: **HTTP Basic** on many Niagara stations (not always SCRAM)
- TLS: `tls_verify = false` for self-signed lab certs only

See also: [vibe_code_apps_17/nhaystack-niagara-pi-tutorial/](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/) — full N4.15 lab with `nhaystack-smoke` CLI. Hub: [rust-lessons/](../vibe_code_apps_17/rust-lessons/README.md).

### Why This Matters

Same building, two protocols: **UDP BACnet** for OT points, **HTTPS Haystack** for semantic tags and ops.

### Mini examples

- Print `/about` server name and Haystack version string.
- Compare response time to a BACnet ReadProperty (qualitative).

### Micro exercises

1. Document which auth mode your station uses (Basic vs SCRAM probe).
2. Build with `--release` before timing.
3. Read `ClientConfig` or equivalent in source.

### Key takeaway

**rusty-haystack sits in the TCP/HTTP layer** of your curriculum—after Days 37–40, before RDF weeks.

### Wireshark Lab

During `about` fetch:

```bash
./capture_pcap.sh day49-haystack-about "tcp port 443 and host 192.168.204.11"
```
