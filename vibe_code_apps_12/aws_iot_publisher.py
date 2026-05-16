"""
AWS IoT Core MQTT 5 publisher for DS18B20 temperature readings (mTLS device cert).

Used by temp_sensor_server.py when --aws-iot is set. Requires: pip install awsiotsdk
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

TIMEOUT_S = 100


def build_payload(deg_c: float, deg_f: float, seq: int, source: str = "ds18b20") -> str:
    return json.dumps(
        {
            "source": source,
            "seq": seq,
            "degC": round(deg_c, 3),
            "degF": round(deg_f, 3),
            "units": {
                "temperature_c": "degreesCelsius",
                "temperature_f": "degreesFahrenheit",
            },
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )


class AwsIotPublisher:
    """Blocking MQTT5 client; call publish() from asyncio via to_thread."""

    def __init__(
        self,
        endpoint: str,
        cert_path: Path,
        key_path: Path,
        client_id: str,
        topic: str,
    ) -> None:
        from awscrt import mqtt5
        from awsiot import mqtt5_client_builder

        self._mqtt5 = mqtt5
        self._topic = topic
        self._seq = 0
        self._connected = threading.Event()

        def on_success(_data: mqtt5.LifecycleConnectSuccessData) -> None:
            self._connected.set()

        self._client = mqtt5_client_builder.mtls_from_path(
            endpoint=endpoint,
            cert_filepath=str(cert_path),
            pri_key_filepath=str(key_path),
            client_id=client_id,
            on_lifecycle_connection_success=on_success,
        )
        self._client.start()
        if not self._connected.wait(TIMEOUT_S):
            raise TimeoutError(f"AWS IoT connect timeout ({endpoint})")

    def publish(self, deg_c: float, deg_f: float) -> None:
        self._seq += 1
        body = build_payload(deg_c, deg_f, self._seq)
        pub = self._client.publish(
            self._mqtt5.PublishPacket(
                topic=self._topic,
                payload=body,
                qos=self._mqtt5.QoS.AT_LEAST_ONCE,
                content_type="application/json",
            )
        )
        pub.result(TIMEOUT_S)

    def close(self) -> None:
        if self._client is not None:
            self._client.stop()
            self._client = None
