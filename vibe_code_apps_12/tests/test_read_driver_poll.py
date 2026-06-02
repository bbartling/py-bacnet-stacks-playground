"""read_driver poll_once regression."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from edge_bacnet.config import PointConfig
from edge_bacnet.read_driver import poll_once


def _point(point_id: str) -> PointConfig:
    return PointConfig(
        device_instance=5007,
        device_address="2000:7@192.168.204.200",
        object_type="analog-input",
        object_instance=10014,
        object_name="STAT ZN-T",
        description="",
        units="degrees-fahrenheit",
        site_id="demo",
        building_id="bens-office",
        system_id="bens-test-bench-box",
        brick_class="",
        brick_tag="",
        poll_interval_s=0,
        point_id=point_id,
        series_id=f"demo#bens-office#bens-test-bench-box#{point_id}",
        object_id="analog-input,10014",
    )


class TestReadDriverPoll(unittest.TestCase):
    def test_poll_once_dry_run_counts(self) -> None:
        pt = _point("5007-analog-input-10014")

        async def _run():
            app = MagicMock()
            with unittest.mock.patch(
                "edge_bacnet.read_driver.read_multiple_chunked",
                new_callable=AsyncMock,
                return_value={"analog-input,10014": 72.5},
            ):
                return await poll_once(
                    app,
                    {(5007, pt.device_address): [pt]},
                    None,
                    dry_run=True,
                    per_point_mqtt=False,
                    site_id="demo",
                    building_id="bens-office",
                )

        total = asyncio.run(_run())
        self.assertEqual(total, 1)

    def test_poll_once_batch_single_publish(self) -> None:
        pt = _point("5007-analog-input-10014")
        publisher = MagicMock()
        publisher._seq = 0

        async def _run():
            app = MagicMock()
            with unittest.mock.patch(
                "edge_bacnet.read_driver.read_multiple_chunked",
                new_callable=AsyncMock,
                return_value={"analog-input,10014": 72.5},
            ):
                return await poll_once(
                    app,
                    {(5007, pt.device_address): [pt]},
                    publisher,
                    dry_run=False,
                    per_point_mqtt=False,
                    site_id="demo",
                    building_id="bens-office",
                )

        total = asyncio.run(_run())
        self.assertEqual(total, 1)
        self.assertEqual(publisher.publish_raw.call_count, 1)
        topic = publisher.publish_raw.call_args[0][0]
        self.assertIn("/batch/telemetry", topic)


if __name__ == "__main__":
    unittest.main()
