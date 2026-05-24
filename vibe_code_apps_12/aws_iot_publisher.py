"""
AWS IoT Core MQTT 5 publisher for DS18B20 temperature readings (mTLS device cert).

Used by temp_sensor_server.py when --aws-iot is set. Requires: pip install awsiotsdk
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

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

    def _publish_raw(self, topic: str, body: str) -> None:
        pub = self._client.publish(
            self._mqtt5.PublishPacket(
                topic=topic,
                payload=body,
                qos=self._mqtt5.QoS.AT_LEAST_ONCE,
                content_type="application/json",
            )
        )
        pub.result(TIMEOUT_S)

    def publish(self, deg_c: float, deg_f: float) -> None:
        self._seq += 1
        body = build_payload(deg_c, deg_f, self._seq)
        self._publish_raw(self._topic, body)

    def publish_messages(self, messages: list[tuple[str, str]]) -> None:
        """Publish one or more (topic, json_body) pairs in order."""
        self._seq += 1
        for topic, body in messages:
            self._publish_raw(topic, body)

    def close(self) -> None:
        if self._client is not None:
            self._client.stop()
            self._client = None


class EdgeMqttConfig:
    """Hierarchical vibe12/{site}/{building}/{system}/{point}/telemetry layout."""

    def __init__(
        self,
        *,
        site_id: str,
        building_id: str,
        system_id: str,
        point_deg_c: str,
        point_deg_f: str,
        brick_class: str = "",
        brick_tag: str = "",
        object_name_c: str = "",
        object_name_f: str = "",
    ) -> None:
        self.site_id = site_id
        self.building_id = building_id
        self.system_id = system_id
        self.point_deg_c = point_deg_c
        self.point_deg_f = point_deg_f
        self.brick_class = brick_class
        self.brick_tag = brick_tag
        self.object_name_c = object_name_c or f"{point_deg_c} °C"
        self.object_name_f = object_name_f or f"{point_deg_f} °F"

    def build_messages(self, deg_c: float, deg_f: float, seq: int) -> list[tuple[str, str]]:
        from edge_bacnet.mqtt_payload import build_edge_payload, mqtt_topic_for_ids

        ts_ms = int(time.time() * 1000)
        common = {
            "site_id": self.site_id,
            "building_id": self.building_id,
            "system_id": self.system_id,
            "seq": seq,
            "ts_ms": ts_ms,
            "brick_class": self.brick_class,
            "brick_tag": self.brick_tag,
        }
        return [
            (
                mqtt_topic_for_ids(
                    self.site_id,
                    self.building_id,
                    self.system_id,
                    self.point_deg_c,
                ),
                build_edge_payload(
                    **common,
                    point_id=self.point_deg_c,
                    value=round(deg_c, 3),
                    unit="degreesCelsius",
                    object_name=self.object_name_c,
                ),
            ),
            (
                mqtt_topic_for_ids(
                    self.site_id,
                    self.building_id,
                    self.system_id,
                    self.point_deg_f,
                ),
                build_edge_payload(
                    **common,
                    point_id=self.point_deg_f,
                    value=round(deg_f, 3),
                    unit="degreesFahrenheit",
                    object_name=self.object_name_f,
                ),
            ),
        ]
