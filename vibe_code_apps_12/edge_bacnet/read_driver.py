"""
Long-lived BACnet RPM read driver → AWS IoT MQTT (hierarchical topics).

  python -m edge_bacnet.read_driver --config points.csv --interval 60 \\
    --iot-endpoint xxx.iot.us-east-2.amazonaws.com \\
    --cert aws_iot_certs/cert.pem --key aws_iot_certs/key.pem \\
    --client-id vibe12-bacnet_pi --site-id demo --building-id bens-office \\
    --name Vibe12Edge --instance 599999 --address 192.168.204.12/24:47809 \\
    --route-aware --network 1 --router-ip 192.168.204.200 --mstp-net 2000

Default: one batch MQTT message per poll cycle (vibe12/{site}/{building}/batch/telemetry).
Use --per-point-mqtt for legacy per-point topics (one Lambda invocation per point).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application

from edge_bacnet.config import group_by_device, load_enabled_points, validate_points
from edge_bacnet.mqtt_payload import (
    bacnet_sample_dict,
    build_bacnet_batch_payload,
    build_bacnet_payload,
    mqtt_batch_topic,
    mqtt_topic_for_point,
)
from edge_bacnet.rpm import read_multiple_chunked


class MqttPublisher:
    """AWS IoT Core MQTT5 client (mTLS device cert)."""

    def __init__(
        self,
        endpoint: str,
        cert_path: Path,
        key_path: Path,
        client_id: str,
    ) -> None:
        from awscrt import mqtt5
        from awsiot import mqtt5_client_builder

        self._mqtt5 = mqtt5
        self._seq = 0
        self._connected = threading.Event()
        self._client = mqtt5_client_builder.mtls_from_path(
            endpoint=endpoint,
            cert_filepath=str(cert_path),
            pri_key_filepath=str(key_path),
            client_id=client_id,
            on_lifecycle_connection_success=lambda _d: self._connected.set(),
        )
        self._client.start()
        if not self._connected.wait(100):
            raise TimeoutError(f"AWS IoT connect timeout ({endpoint})")

    def publish_raw(self, topic: str, payload: str) -> None:
        self._seq += 1
        pub = self._client.publish(
            self._mqtt5.PublishPacket(
                topic=topic,
                payload=payload,
                qos=self._mqtt5.QoS.AT_LEAST_ONCE,
                content_type="application/json",
            )
        )
        pub.result(100)

    def close(self) -> None:
        self._client.stop()


async def poll_once(
    app,
    points_by_device,
    publisher: MqttPublisher | None,
    *,
    dry_run: bool,
    per_point_mqtt: bool,
    site_id: str,
    building_id: str,
) -> int:
    device_keys = list(points_by_device.keys())
    ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    batch_samples: list[dict] = []

    async def _poll_device(device_key, pts):
        dev_inst, dev_addr = device_key
        count = 0
        rpm_objects = {p.rpm_key(): ["present-value"] for p in pts}
        values = await read_multiple_chunked(app, dev_addr, rpm_objects)
        seq = publisher._seq if publisher else count
        for p in pts:
            val = values.get(p.rpm_key())
            if val is None:
                continue
            if per_point_mqtt:
                topic = mqtt_topic_for_point(p)
                payload = build_bacnet_payload(p, val, seq=seq, ts_ms=ts_ms)
                if dry_run:
                    print(f"DRY-RUN {topic} {payload[:120]}...")
                elif publisher:
                    publisher.publish_raw(topic, payload)
            else:
                batch_samples.append(
                    bacnet_sample_dict(p, val, seq=seq, ts_ms=ts_ms)
                )
            count += 1
        return count

    results = await asyncio.gather(
        *[_poll_device(k, points_by_device[k]) for k in device_keys],
        return_exceptions=True,
    )
    total = 0
    for r in results:
        if isinstance(r, Exception):
            print(f"poll error: {r}", file=sys.stderr)
        elif isinstance(r, int):
            total += r

    if not per_point_mqtt and batch_samples and site_id and building_id:
        topic = mqtt_batch_topic(site_id, building_id)
        seq = publisher._seq if publisher else 0
        payload = build_bacnet_batch_payload(
            batch_samples,
            site_id=site_id,
            building_id=building_id,
            seq=seq,
            ts_ms=ts_ms,
        )
        if dry_run:
            print(f"DRY-RUN BATCH {topic} {len(batch_samples)} samples {payload[:120]}...")
        elif publisher:
            publisher.publish_raw(topic, payload)

    return total


async def run_driver(
    config_path: Path,
    *,
    interval_s: float,
    dry_run: bool,
    per_point_mqtt: bool,
    iot_endpoint: str | None,
    cert_path: Path | None,
    key_path: Path | None,
    client_id: str,
    site_id: str | None,
    building_id: str | None,
    bacnet_args=None,
) -> None:
    defaults = {}
    if site_id:
        defaults["site_id"] = site_id
    if building_id:
        defaults["building_id"] = building_id

    points = load_enabled_points(config_path, defaults=defaults or None)
    errors = validate_points(points)
    if errors:
        raise SystemExit("config errors:\n  " + "\n  ".join(errors))

    eff_site = site_id or (points[0].site_id if points else "")
    eff_building = building_id or (points[0].building_id if points else "")
    if not per_point_mqtt and not (eff_site and eff_building):
        raise SystemExit(
            "batch MQTT requires --site-id and --building-id (or CSV defaults)"
        )

    parser = SimpleArgumentParser()
    if bacnet_args is None:
        bacnet_args = parser.parse_args([])

    app = Application.from_args(bacnet_args)
    publisher = None
    if not dry_run:
        if not (iot_endpoint and cert_path and key_path):
            raise SystemExit("--iot-endpoint, --cert, --key required unless --dry-run")
        publisher = MqttPublisher(iot_endpoint, cert_path, key_path, client_id)

    points_by_device = group_by_device(points)
    mode = "per-point" if per_point_mqtt else "batch"
    print(
        f"BACnet read driver: {len(points)} points, {len(points_by_device)} devices, "
        f"interval={interval_s}s dry_run={dry_run} mqtt={mode}",
        file=sys.stderr,
    )

    try:
        while True:
            t0 = time.perf_counter()
            n = await poll_once(
                app,
                points_by_device,
                publisher,
                dry_run=dry_run,
                per_point_mqtt=per_point_mqtt,
                site_id=eff_site,
                building_id=eff_building,
            )
            elapsed = time.perf_counter() - t0
            if per_point_mqtt:
                print(f"published {n} samples in {elapsed:.1f}s", file=sys.stderr)
            else:
                print(f"published batch {n} samples in {elapsed:.1f}s", file=sys.stderr)
            await asyncio.sleep(max(0.0, interval_s - elapsed))
    finally:
        app.close()
        if publisher:
            publisher.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="BACnet RPM read driver → MQTT")
    ap.add_argument("--config", required=True, help="Enabled points CSV")
    ap.add_argument("--interval", type=float, default=30.0, help="Poll interval seconds")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--per-point-mqtt",
        action="store_true",
        help="Legacy: one MQTT message per point (more Lambda invocations)",
    )
    ap.add_argument("--iot-endpoint")
    ap.add_argument("--cert", type=Path)
    ap.add_argument("--key", type=Path)
    ap.add_argument("--client-id", default="vibe12-edge", help="MQTT client ID (must match IoT policy)")
    ap.add_argument("--site-id")
    ap.add_argument("--building-id")
    # accepted for compatibility with discover/service templates; not required by RPM polling
    ap.add_argument("--route-aware", action="store_true")
    ap.add_argument("--network", type=int, default=1)
    ap.add_argument("--router-ip")
    ap.add_argument("--mstp-net", type=int)
    args, bacnet_argv = ap.parse_known_args()

    # Re-inject flags consumed above — MS/TP needs route-aware on the Application.
    bacnet_extra: list[str] = []
    if args.route_aware:
        bacnet_extra.append("--route-aware")
    if args.network is not None:
        bacnet_extra.extend(["--network", str(args.network)])

    bacnet_parser = SimpleArgumentParser()
    bacnet_args = bacnet_parser.parse_args(bacnet_extra + bacnet_argv)

    asyncio.run(
        run_driver(
            Path(args.config),
            interval_s=args.interval,
            dry_run=args.dry_run,
            per_point_mqtt=args.per_point_mqtt,
            iot_endpoint=args.iot_endpoint,
            cert_path=args.cert,
            key_path=args.key,
            client_id=args.client_id,
            site_id=args.site_id,
            building_id=args.building_id,
            bacnet_args=bacnet_args,
        )
    )


if __name__ == "__main__":
    main()
