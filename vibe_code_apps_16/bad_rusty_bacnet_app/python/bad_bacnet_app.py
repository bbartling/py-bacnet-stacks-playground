#!/usr/bin/env python3
"""bad_bacnet_app (Python) — intentionally broken BACnet client for PCAP forensics.

Emulates Open-FDD 802258a anti-patterns using rusty-bacnet Python bindings.
See ../README.md and open-fdd/workspace/reports/BACNET_PCAP_802258A_vs_VIBE16_REPORT.md
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from rusty_bacnet import (
    BACnetClient,
    ObjectIdentifier,
    ObjectType,
    PropertyIdentifier,
)

LOG = logging.getLogger("bad_bacnet_app")


@dataclass
class Target:
    label: str
    device_instance: int
    host: str | None
    object_type: str
    object_instance: int


@dataclass
class Config:
    bind_ip: str
    broadcast: str
    poll_interval_secs: int
    whois_low: int
    whois_high: int
    mstp_network: int
    discover_sleep_secs: int
    dual_loop: bool
    loop_offset_secs: int
    router_ip: str | None
    targets: list[Target]


def load_config(path: Path) -> Config:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    targets = [
        Target(
            label=t["label"],
            device_instance=int(t["device_instance"]),
            host=t.get("host"),
            object_type=t["object_type"],
            object_instance=int(t["object_instance"]),
        )
        for t in data["targets"]
    ]
    return Config(
        bind_ip=data["bind_ip"],
        broadcast=data["broadcast"],
        poll_interval_secs=int(data["poll_interval_secs"]),
        whois_low=int(data["whois_low"]),
        whois_high=int(data["whois_high"]),
        mstp_network=int(data["mstp_network"]),
        discover_sleep_secs=int(data["discover_sleep_secs"]),
        dual_loop=bool(data.get("dual_loop", True)),
        loop_offset_secs=int(data.get("loop_offset_secs", 5)),
        router_ip=data.get("router_ip"),
        targets=targets,
    )


def parse_object_type(name: str) -> ObjectType:
    key = name.lower().replace("-", "_")
    if key in ("analog_input", "ai"):
        return ObjectType.ANALOG_INPUT
    if key in ("analog_value", "av"):
        return ObjectType.ANALOG_VALUE
    raise ValueError(f"unsupported object_type {name}")


def bacnet_addr(host: str, port: int = 47808) -> str:
    return f"{host}:{port}"


async def bad_poll_loop(name: str, cfg: Config, end: float) -> None:
    interval = max(cfg.poll_interval_secs, 5)
    cycle = 0

    while time.monotonic() < end:
        cycle += 1
        LOG.info("[%s] cycle %d — FP-2 new BACnetClient (context manager each cycle)", name, cycle)

        # FP-2: fresh client every cycle — device table discarded on exit
        async with BACnetClient(
            interface=cfg.bind_ip,
            port=0,
            broadcast_address=cfg.broadcast,
            apdu_timeout_ms=6000,
        ) as client:
            # FP-1: broadcast Who-Is entire instance space before every read
            LOG.info(
                "[%s] FP-1 Who-Is %d..%d → broadcast %s",
                name,
                cfg.whois_low,
                cfg.whois_high,
                cfg.broadcast,
            )
            await client.who_is(cfg.whois_low, cfg.whois_high)

            if cfg.router_ip:
                await client.who_is_directed(
                    bacnet_addr(cfg.router_ip),
                    cfg.whois_low,
                    cfg.whois_high,
                )

            for t in cfg.targets:
                if t.host:
                    await client.who_is_directed(
                        bacnet_addr(t.host),
                        t.device_instance,
                        t.device_instance,
                    )

            await asyncio.sleep(cfg.discover_sleep_secs)

            for t in cfg.targets:
                oid = ObjectIdentifier(parse_object_type(t.object_type), t.object_instance)
                try:
                    # FP-4: read_property_from_device — no read_property_routed for MSTP 5007
                    value = await client.read_property_from_device(
                        t.device_instance,
                        oid,
                        PropertyIdentifier.PRESENT_VALUE,
                    )
                    LOG.info(
                        "[%s] FP-4 read %s dev=%d %s:%d = %s",
                        name,
                        t.label,
                        t.device_instance,
                        t.object_type,
                        t.object_instance,
                        value.value,
                    )
                except Exception as err:
                    LOG.warning(
                        "[%s] FP-4 read FAILED %s dev=%d: %s",
                        name,
                        t.label,
                        t.device_instance,
                        err,
                    )

        LOG.info("[%s] FP-2 client stopped — device table discarded", name)
        await asyncio.sleep(interval)


async def run_app(cfg: Config, duration_secs: int) -> None:
    LOG.warning("╔══════════════════════════════════════════════════════════════╗")
    LOG.warning("║  BAD BACNET APP (Python) — intentional anti-patterns        ║")
    LOG.warning("║  Will broadcast Who-Is and hammer the OT network. STOP ME.  ║")
    LOG.warning("╚══════════════════════════════════════════════════════════════╝")

    end = time.monotonic() + duration_secs

    if cfg.dual_loop:
        LOG.info("starting DUAL bad poll loops (simulates bridge + commission)")
        bridge = asyncio.create_task(bad_poll_loop("bridge", cfg, end))
        await asyncio.sleep(cfg.loop_offset_secs)
        commission = asyncio.create_task(bad_poll_loop("commission", cfg, end))
        await asyncio.gather(bridge, commission)
    else:
        await bad_poll_loop("single", cfg, end)

    LOG.info("bad_bacnet_app finished after %ds", duration_secs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "config.toml")
    parser.add_argument("--duration-secs", "--duration", type=int, default=90, dest="duration_secs")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.config.is_file():
        LOG.error("config not found: %s", args.config)
        return 1

    cfg = load_config(args.config)
    try:
        asyncio.run(run_app(cfg, args.duration_secs))
    except KeyboardInterrupt:
        LOG.info("interrupted")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
