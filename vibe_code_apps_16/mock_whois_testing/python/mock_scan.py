#!/usr/bin/env python3
"""mock_scan (Python) — rusty-bacnet twin of the Rust ../src/main.rs demo.

Isolates the open-fdd Who-Is discovery vs local-server socket conflict
(VOLTTRON proxy-agent style):

  a local BACnet server that owns UDP :47808 plus a discovery client on an
  *ephemeral* port cannot both work — broadcast I-Am replies are addressed to
  :47808 and land on the server socket, so the ephemeral client never sees them
  and discovery returns nothing.

open-fdd `client_bind_port()` returns 0 (ephemeral) whenever the local 599999
server is enabled (always on the bench). This reproduces that exact shape.

Scenarios (identical semantics to the Rust binary):
  --bind-port 47808                     WORKING pattern: client owns :47808
  --bind-port 0                         ephemeral client, no server
  --with-local-server --bind-port 0     OPEN-FDD REPRO: server owns :47808, client ephemeral
  --with-local-server --bind-port 47808 proposed fix: client co-binds :47808 (SO_REUSEADDR)

Quick start (Python bindings): https://github.com/jscott3201/rusty-bacnet#quick-start-python
"""

import argparse
import asyncio
import subprocess
import sys

from rusty_bacnet import BACnetClient, BACnetServer


def detect_enp3s0_address():
    try:
        out = subprocess.run(
            ["ip", "-4", "addr", "show", "dev", "enp3s0"],
            capture_output=True, text=True, check=False,
        ).stdout
    except Exception:
        return None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("inet "):
            ip = line.split()[1].split("/")[0]
            return ip
    return None


def subnet_broadcast(ip: str) -> str:
    o = ip.split(".")
    return f"{o[0]}.{o[1]}.{o[2]}.255"


def fmt_mac(mac: bytes) -> str:
    if len(mac) == 6:
        return f"{mac[0]}.{mac[1]}.{mac[2]}.{mac[3]}:{(mac[4] << 8) | mac[5]}"
    return mac.hex()


async def run(args) -> int:
    iface = args.interface or detect_enp3s0_address() or "0.0.0.0"
    bcast = args.broadcast or (
        "255.255.255.255" if iface == "0.0.0.0" else subnet_broadcast(iface)
    )

    print(f"=== scenario: {args.label} ===")
    print(
        f"iface={iface} broadcast={bcast} client_bind_port={args.bind_port} "
        f"with_local_server={args.with_local_server} range={args.low}..{args.high}"
    )

    server = None
    if args.with_local_server:
        # Local server that OWNS :47808 (open-fdd 599999 pattern).
        server = BACnetServer(
            device_instance=args.server_instance,
            device_name="MockLocalServer",
            interface="0.0.0.0",
            port=47808,
            broadcast_address=bcast,
        )
        server.add_analog_input(instance=1, name="mock-local-ai", units=62, present_value=72.5)
        await server.start()
        print(f"local server {args.server_instance} up on :47808 (owns the well-known port)")

    devices = []
    try:
        # Discovery client — port per scenario.
        async with BACnetClient(
            interface=iface,
            port=args.bind_port,
            broadcast_address=bcast,
            apdu_timeout_ms=6000,
        ) as client:
            print(f"sending Who-Is {args.low}..{args.high}")
            await client.who_is(args.low, args.high)
            await asyncio.sleep(args.timeout)
            devices = await client.discovered_devices()
    finally:
        if server is not None:
            await server.stop()

    print(f"\n================ RESULT [{args.label}] ================")
    print(
        f"client_bind_port={args.bind_port} with_local_server={args.with_local_server} "
        f"-> discovered {len(devices)} device(s)"
    )
    instances = sorted(d.object_identifier.instance for d in devices)
    for d in devices:
        print(
            f"  device {d.object_identifier.instance:>7}  "
            f"addr {fmt_mac(d.mac_address):<21}  net={d.source_network}"
        )
    print(f"  instances: {instances}")
    print("=============================================\n")

    if not devices:
        print(
            f"NO devices discovered in scenario '{args.label}' — "
            "if this is the ephemeral+server case, that is the conflict.",
            file=sys.stderr,
        )
    return 0


def main():
    p = argparse.ArgumentParser(description="Reproduce open-fdd Who-Is vs local-server socket conflict")
    p.add_argument("--bind-port", type=int, default=47808,
                   help="discovery client UDP port (0=ephemeral, 47808=well-known)")
    p.add_argument("--with-local-server", action="store_true",
                   help="stand up a local 599999 server on :47808 before scanning")
    p.add_argument("--server-instance", type=int, default=599999)
    p.add_argument("-i", "--interface", default=None, help="local NIC IPv4 (auto-detect enp3s0)")
    p.add_argument("-b", "--broadcast", default=None, help="subnet directed broadcast")
    p.add_argument("--low", type=int, default=0)
    p.add_argument("--high", type=int, default=4_194_303)
    p.add_argument("-t", "--timeout", type=float, default=6.0, help="seconds to wait for I-Am")
    p.add_argument("--label", default="scan")
    args = p.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
