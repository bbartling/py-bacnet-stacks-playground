"""
DS18B20 1-Wire digital temperature helpers for Raspberry Pi OS.

Reads the kernel `w1_slave` sysfs file exposed when `w1-gpio` is enabled
(typically GPIO4, physical pin 7). No extra Python packages required.

Datasheet: https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

W1_DEVICES = Path("/sys/bus/w1/devices")


def parse_w1_slave(contents: str) -> float:
    """
    Parse `w1_slave` output and return temperature in °C.

    Expects the second line to contain ``t=`` in millidegrees (integer).
    """
    lines = [ln.strip() for ln in contents.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        raise ValueError("w1_slave: expected at least 2 lines")

    if "YES" not in lines[0]:
        raise ValueError(f"w1_slave CRC not OK (first line): {lines[0]!r}")

    for token in lines[1].split():
        if token.startswith("t="):
            milli_c = int(token[2:])
            return milli_c / 1000.0

    raise ValueError(f"w1_slave: no t= token in {lines[1]!r}")


def discover_ds18b20_dirs() -> list[Path]:
    """Return sorted list of device dirs under sysfs (names like ``28-00000abcdef``)."""
    if not W1_DEVICES.is_dir():
        return []
    return sorted(p for p in W1_DEVICES.iterdir() if p.is_dir() and p.name.startswith("28-"))


class Ds18b20SysfsReader:
    """
    Read a DS18B20 via Linux 1-Wire sysfs (``.../w1_slave``).

    Parameters
    ----------
    device_id:
        Folder name under ``/sys/bus/w1/devices/``, e.g. ``28-0315977934ff``.
        If omitted, a single auto-detected ``28-*`` device is required.
    w1_slave_path:
        Full path to a ``w1_slave`` file; overrides ``device_id`` when set.
    """

    def __init__(
        self,
        device_id: Optional[str] = None,
        w1_slave_path: Optional[str] = None,
    ) -> None:
        if w1_slave_path:
            self._slave = Path(w1_slave_path)
        elif device_id:
            self._slave = W1_DEVICES / device_id / "w1_slave"
        else:
            found = discover_ds18b20_dirs()
            if not found:
                raise FileNotFoundError(
                    "No DS18B20 under /sys/bus/w1/devices/28-* — enable 1-Wire "
                    "(dtoverlay=w1-gpio,gpio=4) and reboot, or pass --w1-device."
                )
            if len(found) > 1:
                ids = ", ".join(p.name for p in found)
                raise RuntimeError(
                    f"Multiple DS18B20 devices: {ids}. Pass --w1-device <one of these>."
                )
            self._slave = found[0] / "w1_slave"

        if not self._slave.is_file():
            raise FileNotFoundError(f"w1_slave not found: {self._slave}")

    def read_celsius(self) -> float:
        text = self._slave.read_text(encoding="utf-8", errors="replace")
        return parse_w1_slave(text)
