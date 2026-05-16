#!/usr/bin/env python3
"""
Publish fake DS18B20-style temperature readings to AWS IoT Core (MQTT 5, mTLS).

Prerequisites (same as start.sh):
  - Unzipped connect_device_package.zip in this directory
  - pip install ./aws-iot-device-sdk-python-v2  (or run ./start.sh once)

Policy on this thing allows client_id basicPubSub and topic sdk/test/python.

Example (use the same Python where you ran start.sh / awsiot is installed):
  ../env/bin/python publish_fake_temp.py --count 5 --interval 2 
  ../env/bin/python publish_fake_temp.py --count 0 --interval 2   # until Ctrl+C

AWS console: MQTT test client → Subscribe to sdk/test/python
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from awscrt import mqtt5
from awsiot import mqtt5_client_builder

TIMEOUT_S = 100
HERE = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _fake_reading(seq: int, base_c: float) -> dict:
    # Gentle drift so the MQTT test client graph looks alive
    c = base_c + random.uniform(-0.4, 0.4) + 0.15 * (seq % 7)
    f = c * 9.0 / 5.0 + 32.0
    return {
        "source": "fake-ds18b20",
        "seq": seq,
        "degC": round(c, 3),
        "degF": round(f, 3),
        "units": {"temperature_c": "degreesCelsius", "temperature_f": "degreesFahrenheit"},
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    _load_dotenv(HERE / ".env")

    parser = argparse.ArgumentParser(description="Publish fake temp JSON to AWS IoT Core")
    parser.add_argument(
        "--endpoint",
        default=_env("AWS_IOT_ENDPOINT", "a2ab6ncd4xlhhr-ats.iot.us-east-2.amazonaws.com"),
    )
    parser.add_argument(
        "--cert",
        type=Path,
        default=HERE / _env("AWS_IOT_CERT_PEM", "vibe-code-app-12-temp-sensor.cert.pem"),
    )
    parser.add_argument(
        "--key",
        type=Path,
        default=HERE / _env("AWS_IOT_PRIVATE_KEY", "vibe-code-app-12-temp-sensor.private.key"),
    )
    parser.add_argument(
        "--client-id",
        default=_env("AWS_IOT_CLIENT_ID", "basicPubSub"),
        help="Must match IoT policy (default basicPubSub)",
    )
    parser.add_argument(
        "--topic",
        default=_env("AWS_IOT_TOPIC", "sdk/test/python"),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Messages to send (0 = until Ctrl+C)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Seconds between publishes",
    )
    parser.add_argument(
        "--base-c",
        type=float,
        default=24.0,
        help="Center temperature for fake readings (°C)",
    )
    parser.add_argument(
        "--subscribe",
        action="store_true",
        help="Also subscribe to the topic (see your own messages in this terminal)",
    )
    args = parser.parse_args()

    if not args.cert.is_file():
        print(f"Missing certificate: {args.cert}", file=sys.stderr)
        print("Unzip connect_device_package.zip in this folder first.", file=sys.stderr)
        return 1
    if not args.key.is_file():
        print(f"Missing private key: {args.key}", file=sys.stderr)
        return 1

    try:
        import awsiot  # noqa: F401
    except ImportError:
        print("awsiot not installed. Run: pip install ./aws-iot-device-sdk-python-v2", file=sys.stderr)
        return 1

    connected = threading.Event()

    def on_connection_success(_data: mqtt5.LifecycleConnectSuccessData) -> None:
        print(f"Connected to {args.endpoint} as {args.client_id}")
        connected.set()

    def on_publish_received(data: mqtt5.PublishReceivedData) -> None:
        pkt = data.publish_packet
        print(f"<< {pkt.topic}: {pkt.payload.decode('utf-8', errors='replace')}")

    client = mqtt5_client_builder.mtls_from_path(
        endpoint=args.endpoint,
        cert_filepath=str(args.cert),
        pri_key_filepath=str(args.key),
        client_id=args.client_id,
        on_lifecycle_connection_success=on_connection_success,
        on_publish_received=on_publish_received if args.subscribe else None,
    )

    client.start()
    if not connected.wait(TIMEOUT_S):
        print("Connection timeout", file=sys.stderr)
        return 1

    if args.subscribe:
        sub = client.subscribe(
            subscribe_packet=mqtt5.SubscribePacket(
                subscriptions=[
                    mqtt5.Subscription(topic_filter=args.topic, qos=mqtt5.QoS.AT_LEAST_ONCE)
                ]
            )
        )
        sub.result(TIMEOUT_S)
        print(f"Subscribed to {args.topic}")

    seq = 0
    try:
        while args.count == 0 or seq < args.count:
            seq += 1
            payload = _fake_reading(seq, args.base_c)
            body = json.dumps(payload)
            print(f">> {args.topic}: {body}")
            pub = client.publish(
                mqtt5.PublishPacket(
                    topic=args.topic,
                    payload=body,
                    qos=mqtt5.QoS.AT_LEAST_ONCE,
                    content_type="application/json",
                )
            )
            ack = pub.result(TIMEOUT_S)
            print(f"   PubAck {ack.puback.reason_code}")
            if args.count == 0 or seq < args.count:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")

    client.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
