#!/usr/bin/env python3
"""Read fake Niagara history through pyhaystack's grid operations.

pyhaystack's built-in Niagara 4 session targets Niagara's proprietary web
login endpoints.  This adapter performs standard Haystack SCRAM with the
fixture client, then lets pyhaystack encode/decode the read-only grid calls.
"""

from __future__ import annotations

import argparse
from urllib.parse import urlsplit, urlunsplit

import hszinc
from pyhaystack.client.session import HaystackSession

from fake_niagara.client import HaystackClient


class StandardAuthPyHaystackSession(HaystackSession):
    """Minimal read-only pyhaystack session using a standard bearer token."""

    def __init__(self, api_url: str, username: str, password: str) -> None:
        api_url = api_url.rstrip("/")
        parsed = urlsplit(api_url)
        api_dir = parsed.path.strip("/")
        if not api_dir:
            raise ValueError("api_url must include the API path, such as /api")
        origin = urlunsplit((parsed.scheme, parsed.netloc, "/", "", ""))

        authenticator = HaystackClient(api_url, username, password)
        token = authenticator.authenticate()
        super().__init__(
            origin,
            api_dir,
            grid_format=hszinc.MODE_ZINC,
            pint=False,
            http_args={
                "headers": {"Authorization": f"BEARER authToken={token}"},
                "timeout": 10,
            },
        )
        self._username = username

    @property
    def is_logged_in(self) -> bool:
        return True

    def _on_read(self, ids, filter_expr, limit, callback, **kwargs):
        grid = hszinc.Grid()
        if ids is not None:
            if isinstance(ids, (str, hszinc.Ref)):
                ids = [ids]
            grid.column["id"] = {}
            grid.extend({"id": self._obj_to_ref(item)} for item in ids)
        else:
            grid.column["filter"] = {}
            row = {"filter": filter_expr}
            if limit is not None:
                grid.column["limit"] = {}
                row["limit"] = int(limit)
            grid.append(row)
        return self._post_grid(
            "read",
            grid,
            callback,
            post_format=hszinc.MODE_ZINC,
            expect_format=hszinc.MODE_ZINC,
            **kwargs,
        )

    def _on_his_read(self, point, rng, callback, **kwargs):
        grid = hszinc.Grid()
        grid.column["id"] = {}
        grid.column["range"] = {}
        grid.append({"id": self._obj_to_ref(point), "range": rng})
        return self._post_grid(
            "hisRead",
            grid,
            callback,
            post_format=hszinc.MODE_ZINC,
            expect_format=hszinc.MODE_ZINC,
            **kwargs,
        )

    def logout(self) -> None:
        # This short-lived example leaves token expiry to the fixture server.
        pass


def completed(operation, timeout: float = 10.0):
    operation.wait(timeout)
    if not operation.is_done:
        raise TimeoutError("pyhaystack operation timed out")
    return operation.result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080/api")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="demo")
    parser.add_argument("--range", dest="range_text", default="yesterday")
    args = parser.parse_args()

    session = StandardAuthPyHaystackSession(args.url, args.username, args.password)
    points = completed(session.read(filter_expr="point and his"))
    if not points:
        raise RuntimeError("server returned no historized points")

    point = points[0]
    history = completed(session.his_read(point["id"], args.range_text))
    print(f"discovered_points={len(points)}")
    print(f"point={point['id'].name}")
    print(f"history_rows={len(history)}")
    if history:
        print(f"first={history[0]}")
        print(f"last={history[-1]}")


if __name__ == "__main__":
    main()
