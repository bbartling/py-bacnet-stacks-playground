# discover-and-poll (Day 46)

BACnet commission capstone skeleton. Builds without [rusty-bacnet](https://github.com/jscott3201/rusty-bacnet); wire the stack after Day 41.

## Build

```bash
cargo build --release
./target/release/discover-and-poll --help
```

## Examples

```bash
# Discovery stub (UDP bind + placeholder row)
cargo run -- discover --bind 0.0.0.0:47808
cargo run -- discover --bind 0.0.0.0:47808 --device 5007

# Poll stub → commission_snapshot.csv
cargo run -- poll --device 5007 --host 192.168.204.200 \\
  --objects analogInput:1 --objects analogInput:2
```

## Wireshark

```bash
cd ../../lab-scripts
./capture_pcap.sh day46-capstone "udp port 47808 and host 192.168.204.200"
```

Filter: `udp.port == 47808 && bacnet`

## Lesson

[Day 46](../../day46.md) · [Capstone README](../README.md)
