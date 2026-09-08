"""CLI argv handling for BACnet passthrough."""

import argparse


def _strip_bacnet_argv(argv: list[str]) -> list[str]:
    """Mirror vibe24.cli: allow ``serve --bacnet -- --address …``."""
    if argv and argv[0] == "--":
        return argv[1:]
    return argv


def test_bacnet_separator_stripped():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--bacnet", action="store_true")
    args, unknown = parser.parse_known_args(
        ["serve", "--bacnet", "--", "--address", "127.0.0.1/32:47808", "--name", "Twin"]
    )
    bacnet_argv = _strip_bacnet_argv(unknown)
    assert args.bacnet is True
    assert bacnet_argv == ["--address", "127.0.0.1/32:47808", "--name", "Twin"]
