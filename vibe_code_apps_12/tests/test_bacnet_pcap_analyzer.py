"""Regression tests for the BACnet pcap analyzer."""

from __future__ import annotations

import subprocess
import struct
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "analyze_bacnet_pcap.py"


def _ipv4_udp(src_ip: bytes, dst_ip: bytes, src_port: int, dst_port: int, payload: bytes) -> bytes:
    total_length = 20 + 8 + len(payload)
    ipv4 = bytearray(20)
    ipv4[0] = 0x45
    ipv4[2:4] = struct.pack("!H", total_length)
    ipv4[8] = 64
    ipv4[9] = 17
    ipv4[12:16] = src_ip
    ipv4[16:20] = dst_ip

    udp = struct.pack("!HHHH", src_port, dst_port, 8 + len(payload), 0)
    return bytes(ipv4) + udp + payload


def _sll2_frame(ip_packet: bytes) -> bytes:
    header = bytearray(20)
    header[0:2] = struct.pack("!H", 0x0800)
    return bytes(header) + ip_packet


def _bacnet_payload(apdu: bytes) -> bytes:
    npdu = b"\x01\x00"
    length = 4 + len(npdu) + len(apdu)
    return b"\x81\x0a" + struct.pack("!H", length) + npdu + apdu


def _write_pcap(path: Path, packets: list[tuple[int, bytes]]) -> None:
    with path.open("wb") as fh:
        fh.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 276))
        for ts_usec, frame in packets:
            fh.write(struct.pack("<IIII", ts_usec, 0, len(frame), len(frame)))
            fh.write(frame)


class TestBacnetPcapAnalyzer(unittest.TestCase):
    def test_summary_counts_request_types(self) -> None:
        request = _sll2_frame(
            _ipv4_udp(
                b"\xc0\xa8\x01\x0a",
                b"\xc0\xa8\x01\x14",
                47809,
                47808,
                _bacnet_payload(b"\x00\x05\x01\x0e"),
            )
        )
        who_is = _sll2_frame(
            _ipv4_udp(
                b"\xc0\xa8\x01\x14",
                b"\xff\xff\xff\xff",
                47808,
                47809,
                _bacnet_payload(b"\x10\x08"),
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pcap = Path(tmpdir) / "sample.pcap"
            _write_pcap(pcap, [(1, request), (1, who_is)])

            result = subprocess.run(
                [sys.executable, str(_SCRIPT), str(pcap), "--top", "5"],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertIn("BACnet request packets: 2", result.stdout)
        self.assertIn("confirmed ReadPropertyMultiple (14)", result.stdout)
        self.assertIn("unconfirmed Who-Is (8)", result.stdout)
        self.assertIn("minute 00: 2", result.stdout)


if __name__ == "__main__":
    unittest.main()
