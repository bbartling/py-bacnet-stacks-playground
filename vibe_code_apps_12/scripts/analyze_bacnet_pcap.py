#!/usr/bin/env python3
"""Summarize BACnet request frequency from a tcpdump pcap.

The script is dependency-free and understands the link types produced by
`tcpdump -i any` on Linux (SLL and SLL2) as well as Ethernet captures.
"""

from __future__ import annotations

import argparse
import datetime as dt
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

BACNET_PORTS = {47808, 47809}

PDU_NAMES = {
    0x0: "confirmed",
    0x1: "unconfirmed",
    0x2: "simple-ack",
    0x3: "complex-ack",
    0x4: "segmented-ack",
    0x5: "error",
    0x6: "reject",
    0x7: "abort",
}

CONFIRMED_SERVICES = {
    0: "AcknowledgeAlarm",
    1: "ConfirmedCOVNotification",
    2: "ConfirmedEventNotification",
    3: "GetAlarmSummary",
    4: "GetEnrollmentSummary",
    5: "SubscribeCOV",
    6: "AtomicReadFile",
    7: "AtomicWriteFile",
    8: "AddListElement",
    9: "RemoveListElement",
    10: "CreateObject",
    11: "DeleteObject",
    12: "ReadProperty",
    13: "ReadPropertyConditional",
    14: "ReadPropertyMultiple",
    15: "WriteProperty",
    16: "WritePropertyMultiple",
    17: "DeviceCommunicationControl",
    18: "ConfirmedPrivateTransfer",
    19: "ConfirmedTextMessage",
    20: "ReinitializeDevice",
    21: "VTOpen",
    22: "VTClose",
    23: "VTData",
    24: "Authenticate",
    25: "RequestKey",
    26: "ReadRange",
    27: "LifeSafetyOperation",
    28: "SubscribeCOVProperty",
    29: "GetEventInformation",
    30: "WriteGroup",
    31: "SubscribeCOVPropertyMultiple",
}

UNCONFIRMED_SERVICES = {
    0: "I-Am",
    1: "I-Have",
    2: "UnconfirmedCOVNotification",
    3: "UnconfirmedEventNotification",
    4: "UnconfirmedPrivateTransfer",
    5: "UnconfirmedTextMessage",
    6: "TimeSynchronization",
    7: "Who-Has",
    8: "Who-Is",
    9: "UTCTimeSynchronization",
    10: "WriteGroup",
}


@dataclass(frozen=True)
class BacnetRequest:
    timestamp: float
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    pdu_type: str
    service_code: int
    service_name: str

    @property
    def flow_key(self) -> str:
        return f"{self.src_ip}:{self.src_port} -> {self.dst_ip}:{self.dst_port}"

    @property
    def request_key(self) -> str:
        return f"{self.pdu_type} {self.service_name} ({self.service_code})"


def _pcap_endian_and_divisor(magic: bytes) -> tuple[str, int, int]:
    if magic == b"\xd4\xc3\xb2\xa1":
        return "<", 1_000_000, 0
    if magic == b"\xa1\xb2\xc3\xd4":
        return ">", 1_000_000, 0
    if magic == b"\x4d\x3c\xb2\xa1":
        return "<", 1_000_000_000, 0
    if magic == b"\xa1\xb2\x3c\x4d":
        return ">", 1_000_000_000, 0
    raise ValueError("unsupported pcap magic")


def _read_pcap_packets(path: Path):
    with path.open("rb") as fh:
        magic = fh.read(4)
        if len(magic) != 4:
            raise ValueError("empty or truncated pcap")
        endian, divisor, _ = _pcap_endian_and_divisor(magic)
        header = fh.read(20)
        if len(header) != 20:
            raise ValueError("truncated pcap global header")
        _version_major, _version_minor, _thiszone, _sigfigs, _snaplen, linktype = struct.unpack(
            endian + "HHiiii", header
        )
        while True:
            rec = fh.read(16)
            if not rec:
                break
            if len(rec) != 16:
                raise ValueError("truncated pcap packet header")
            ts_sec, ts_frac, incl_len, _orig_len = struct.unpack(endian + "IIII", rec)
            data = fh.read(incl_len)
            if len(data) != incl_len:
                raise ValueError("truncated pcap packet payload")
            yield ts_sec + (ts_frac / divisor), linktype, data


def _unwrap_link_layer(linktype: int, data: bytes) -> tuple[int, bytes] | None:
    if linktype == 1:  # Ethernet
        if len(data) < 14:
            return None
        return struct.unpack("!H", data[12:14])[0], data[14:]
    if linktype == 113:  # Linux cooked capture v1
        if len(data) < 16:
            return None
        return struct.unpack("!H", data[14:16])[0], data[16:]
    if linktype == 276:  # Linux cooked capture v2
        if len(data) < 20:
            return None
        return struct.unpack("!H", data[0:2])[0], data[20:]
    return None


def _parse_ipv4_udp(data: bytes) -> tuple[str, str, int, int, bytes] | None:
    if len(data) < 20:
        return None
    version = data[0] >> 4
    ihl = (data[0] & 0x0F) * 4
    if version != 4 or ihl < 20 or len(data) < ihl + 8:
        return None
    if data[9] != 17:
        return None
    src_ip = ".".join(str(b) for b in data[12:16])
    dst_ip = ".".join(str(b) for b in data[16:20])
    src_port, dst_port, _udp_len = struct.unpack("!HHH", data[ihl : ihl + 6])
    return src_ip, dst_ip, src_port, dst_port, data[ihl + 8 :]


def _npdu_apdu_offset(payload: bytes) -> int | None:
    if len(payload) < 2 or payload[0] != 1:
        return None
    control = payload[1]
    if control & 0x80:
        return None

    offset = 2
    if control & 0x20:
        if len(payload) < offset + 3:
            return None
        dlen = payload[offset + 2]
        offset += 3 + dlen
    if control & 0x08:
        if len(payload) < offset + 3:
            return None
        slen = payload[offset + 2]
        offset += 3 + slen
    if control & (0x20 | 0x08):
        if len(payload) < offset + 1:
            return None
        offset += 1
    return offset


def _service_name(pdu_type: int, service_code: int) -> str:
    if pdu_type == 0x0:
        return CONFIRMED_SERVICES.get(service_code, f"confirmed-{service_code}")
    if pdu_type == 0x1:
        return UNCONFIRMED_SERVICES.get(service_code, f"unconfirmed-{service_code}")
    return PDU_NAMES.get(pdu_type, f"pdu-{pdu_type}")


def _extract_request(timestamp: float, linktype: int, frame: bytes) -> BacnetRequest | None:
    unwrap = _unwrap_link_layer(linktype, frame)
    if unwrap is None:
        return None
    ethertype, ip_payload = unwrap
    if ethertype != 0x0800:
        return None

    ipv4 = _parse_ipv4_udp(ip_payload)
    if ipv4 is None:
        return None
    src_ip, dst_ip, src_port, dst_port, udp_payload = ipv4
    if src_port not in BACNET_PORTS and dst_port not in BACNET_PORTS:
        return None

    if len(udp_payload) < 4 or udp_payload[0] != 0x81:
        return None
    bacnet_length = struct.unpack("!H", udp_payload[2:4])[0]
    bacnet_payload = udp_payload[4:bacnet_length]
    apdu_offset = _npdu_apdu_offset(bacnet_payload)
    if apdu_offset is None or len(bacnet_payload) <= apdu_offset:
        return None

    pdu_type = bacnet_payload[apdu_offset] >> 4
    if pdu_type not in (0x0, 0x1):
        return None

    if pdu_type == 0x0:
        if len(bacnet_payload) < apdu_offset + 4:
            return None
        service_code = bacnet_payload[apdu_offset + 3]
    else:
        if len(bacnet_payload) < apdu_offset + 2:
            return None
        service_code = bacnet_payload[apdu_offset + 1]

    return BacnetRequest(
        timestamp=timestamp,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        pdu_type=PDU_NAMES[pdu_type],
        service_code=service_code,
        service_name=_service_name(pdu_type, service_code),
    )


def analyze(path: Path) -> dict[str, object]:
    packets = 0
    bacnet_packets = 0
    requests: list[BacnetRequest] = []
    start_ts = None
    end_ts = None
    linktype = None

    for timestamp, this_linktype, frame in _read_pcap_packets(path):
        packets += 1
        if start_ts is None:
            start_ts = timestamp
            linktype = this_linktype
        end_ts = timestamp
        request = _extract_request(timestamp, this_linktype, frame)
        if request is not None:
            bacnet_packets += 1
            requests.append(request)

    if start_ts is None or end_ts is None:
        raise ValueError("pcap contains no packets")

    request_counter = Counter(req.request_key for req in requests)
    flow_counter = Counter(req.flow_key for req in requests)
    minute_counter = Counter(int((req.timestamp - start_ts) // 60) for req in requests)

    return {
        "path": path,
        "packets": packets,
        "bacnet_packets": bacnet_packets,
        "requests": requests,
        "request_counter": request_counter,
        "flow_counter": flow_counter,
        "minute_counter": minute_counter,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "linktype": linktype,
    }


def _fmt_ts(timestamp: float) -> str:
    return dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _print_summary(summary: dict[str, object], top_n: int) -> None:
    requests: list[BacnetRequest] = summary["requests"]  # type: ignore[assignment]
    request_counter: Counter[str] = summary["request_counter"]  # type: ignore[assignment]
    flow_counter: Counter[str] = summary["flow_counter"]  # type: ignore[assignment]
    minute_counter: Counter[int] = summary["minute_counter"]  # type: ignore[assignment]
    start_ts = summary["start_ts"]  # type: ignore[assignment]
    end_ts = summary["end_ts"]  # type: ignore[assignment]
    duration = max(float(end_ts) - float(start_ts), 0.0)
    rate = len(requests) / duration if duration > 0 else float(len(requests))

    print(f"PCAP: {summary['path']}")
    print(f"Linktype: {summary['linktype']}")
    print(f"Capture window: {_fmt_ts(float(start_ts))} -> {_fmt_ts(float(end_ts))} ({duration:.1f}s)")
    print(f"Packets: {summary['packets']}")
    print(f"BACnet request packets: {summary['bacnet_packets']}")
    print(f"Request rate: {rate:.2f}/s")
    print()
    print("Top request types:")
    for request_key, count in request_counter.most_common(top_n):
        print(f"  {request_key:<42} {count:>6}  {count / duration if duration > 0 else float(count):>7.2f}/s")
    if not request_counter:
        print("  (no BACnet requests found)")
    print()
    print("Top request flows:")
    for flow_key, count in flow_counter.most_common(top_n):
        print(f"  {flow_key:<42} {count:>6}")
    if not flow_counter:
        print("  (no BACnet flows found)")
    print()
    print("Requests per minute:")
    for minute in sorted(minute_counter):
        print(f"  minute {minute:02d}: {minute_counter[minute]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pcap", type=Path, help="path to a BACnet pcap")
    parser.add_argument("--top", type=int, default=10, help="number of rows to print per section")
    args = parser.parse_args(argv)

    try:
        summary = analyze(args.pcap)
        _print_summary(summary, max(1, args.top))
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
