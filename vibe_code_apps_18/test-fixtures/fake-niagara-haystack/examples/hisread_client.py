"""A copy/paste-friendly client smoke test for an open FDD experiment.

Run the server first, then:
    python examples/hisread_client.py --url http://raspberrypi.local:8080/api
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fake_niagara.client import HaystackClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080/api")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="demo")
    parser.add_argument("--range", default="yesterday")
    args = parser.parse_args()
    client = HaystackClient(args.url, args.username, args.password)
    try:
        points = client.read("point and his")
        print(f"found {len(points.rows)} history points")
        for point in points.rows:
            point_id = point["id"].value
            history = client.his_read(point_id, args.range)
            print(f"{point_id:24} {point.get('dis', ''):38} {len(history.rows):4} records")
            if history.rows:
                print(f"  first={history.rows[0]['ts']} value={history.rows[0]['val']}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
