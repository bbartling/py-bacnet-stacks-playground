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
        "--plant",
        choices=("surrogate", "eplus"),
        default="surrogate",
        help="Physics backend: surrogate ODE (default) or vibe23 residential EnergyPlus day",
    )
    serve.add_argument(
        "--eplus-month",
        type=int,
        default=7,
        help="EnergyPlus run-period month (with --plant eplus)",
    )
    serve.add_argument(
        "--eplus-day",
        type=int,
        default=15,
        help="EnergyPlus run-period day (with --plant eplus)",
    )
    serve.add_argument(
        "--wall-seconds-per-sim-minute",
        type=float,
        default=12.0,
        help="Plant tick period in wall seconds (12 ≈ 5x realtime; UI slider can change live)",
    )

    args, bacnet_argv = parser.parse_known_args(argv)
    if args.cmd != "serve":
        parser.error("unknown command")

    # Allow: vibe24 serve --bacnet -- --address ...  (strip argparse/-- separator)
    if bacnet_argv and bacnet_argv[0] == "--":
        bacnet_argv = bacnet_argv[1:]

    logging.basicConfig(level=logging.INFO)
    from .api import create_app
    from .runtime import TwinRuntime

    plant: object
    if args.plant == "eplus":
        from .eplus_plant import EnergyPlusPlant

        plant = EnergyPlusPlant(month=int(args.eplus_month), day=int(args.eplus_day))
    else:
        from .plant import SurrogatePlant

        plant = SurrogatePlant()

    runtime = TwinRuntime(
        plant=plant,
        wall_seconds_per_sim_minute=float(args.wall_seconds_per_sim_minute),
    )
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
