"""CLI entry for the live twin."""
from __future__ import annotations

import argparse
import asyncio
import logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vibe24", description="Vibe 24 live BACnet + physics twin")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Run FastAPI dashboard (+ optional BACnet)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8024)
    serve.add_argument("--bacnet", action="store_true", help="Also start BACpypes3 device")
    serve.add_argument(
        "--wall-seconds-per-sim-minute",
        type=float,
        default=1.0,
        help="Plant tick period in wall seconds (1.0 ≈ real-time minutes)",
    )

    args, bacnet_argv = parser.parse_known_args(argv)
    if args.cmd != "serve":
        parser.error("unknown command")

    logging.basicConfig(level=logging.INFO)
    from .api import create_app
    from .runtime import TwinRuntime

    runtime = TwinRuntime(wall_seconds_per_sim_minute=float(args.wall_seconds_per_sim_minute))
    app = create_app(runtime)

    if args.bacnet:
        import uvicorn

        async def _both() -> None:
            from .bacnet_device import run_bacnet_device

            config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
            server = uvicorn.Server(config)
            await asyncio.gather(server.serve(), run_bacnet_device(runtime, bacnet_argv))

        asyncio.run(_both())
        return 0

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
