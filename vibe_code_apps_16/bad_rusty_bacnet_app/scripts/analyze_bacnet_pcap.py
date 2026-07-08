#!/usr/bin/env python3
"""Analyze BACnet PCAP from openfdd-bacnet-feather-concept soak.

Validates captured UDP/47808 traffic against scripts/bacnet_pcap_expectations.toml:
  - Poll cadence per peer host
  - Request/response balance to configured routers/devices
  - Foreign :47808 binders (network takeover risk)
  - Broadcast Who-Is / I-Am storms
  - BVLC function mix (unicast vs forwarded routed)

Uses dpkt if available; falls back to tcpdump text parse.

Usage:
  python scripts/analyze_bacnet_pcap.py --pcap data/exports/pcap/bacnet_soak.pcap
  python scripts/analyze_bacnet_pcap.py --pcap ... --duration 1200 --json-out report.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTATIONS = Path(__file__).with_name("bad_pcap_expectations.toml")

# BACnet/IP BVLC
BVLC_TYPE_BACNET_IP = 0x81
BVLC_ORIGINAL_UNICAST_NPDU = 0x0A
BVLC_ORIGINAL_BROADCAST_NPDU = 0x0B
BVLC_FORWARDED_NPDU = 0x04
BVLC_REGISTER_FOREIGN_DEVICE = 0x05
BVLC_DISTRIBUTE_BROADCAST = 0x09

# APDU service choices (subset)
APDU_CONFIRMED_REQUEST = 0
APDU_UNCONFIRMED_REQUEST = 1
APDU_SIMPLE_ACK = 2
APDU_COMPLEX_ACK = 3
APDU_ERROR = 5
APDU_REJECT = 6

UNCONFIRMED_WHO_IS = 0x08
UNCONFIRMED_I_AM = 0x00
CONFIRMED_READ_PROPERTY = 0x0C


@dataclass
class PacketRecord:
    ts: float
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    length: int
    bvlc_function: int | None = None
    npdu_control: int | None = None
    apdu_type: int | None = None
    service_choice: int | None = None
    is_broadcast: bool = False


@dataclass
class AnalysisReport:
    pcap: str
    duration_secs: float
    total_packets: int = 0
    bacnet_packets: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    passes: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    verdict: str = "UNKNOWN"

    def to_dict(self) -> dict:
        return {
            "pcap": self.pcap,
            "duration_secs": self.duration_secs,
            "total_packets": self.total_packets,
            "bacnet_packets": self.bacnet_packets,
            "verdict": self.verdict,
            "passes": self.passes,
            "warnings": self.warnings,
            "errors": self.errors,
            "stats": self.stats,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }


def load_expectations(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def parse_bacnet_udp(payload: bytes) -> tuple[int | None, int | None, int | None, int | None, bool]:
    """Return bvlc_function, npdu_control, apdu_type, service_choice, is_broadcast."""
    if len(payload) < 4 or payload[0] != BVLC_TYPE_BACNET_IP:
        return None, None, None, None, False
    bvlc_len = int.from_bytes(payload[2:4], "big")
    if bvlc_len < 4 or len(payload) < bvlc_len:
        return None, None, None, None, False
    func = payload[1]
    is_bcast = func in (BVLC_ORIGINAL_BROADCAST_NPDU, BVLC_DISTRIBUTE_BROADCAST)
    offset = 4
    if func == BVLC_FORWARDED_NPDU:
        # 6-byte MAC + optional DNET/DADR hop count
        if len(payload) < offset + 6:
            return func, None, None, None, is_bcast
        offset += 6
        if offset < len(payload) and payload[offset] == 0x01:
            offset += 1
            dnet = int.from_bytes(payload[offset : offset + 2], "big")
            offset += 2
            dlen = payload[offset]
            offset += 1 + dlen
    npdu_control = None
    apdu_type = None
    service = None
    if offset + 2 <= len(payload):
        # skip version + control
        npdu_control = payload[offset + 1]
        apdu_off = offset + 2
        if npdu_control & 0x80:
            # network layer message — skip for now
            return func, npdu_control, None, None, is_bcast
        if apdu_off < len(payload):
            apdu_type = (payload[apdu_off] & 0xF0) >> 4
            if apdu_type == APDU_UNCONFIRMED_REQUEST:
                if apdu_off + 1 < len(payload):
                    service = payload[apdu_off + 1]
            elif apdu_type == APDU_CONFIRMED_REQUEST:
                # invoke id at +1, service choice at +2
                if apdu_off + 2 < len(payload):
                    service = payload[apdu_off + 2]
            elif apdu_type in (APDU_SIMPLE_ACK, APDU_COMPLEX_ACK, APDU_ERROR, APDU_REJECT):
                if apdu_off + 2 < len(payload):
                    service = payload[apdu_off + 2]
    return func, npdu_control, apdu_type, service, is_bcast


def read_pcap_dpkt(pcap_path: Path, poller_ip: str | None = None) -> list[PacketRecord]:
    import dpkt  # type: ignore

    records: list[PacketRecord] = []
    with pcap_path.open("rb") as fh:
        pcap = dpkt.pcap.Reader(fh)
        t0 = None
        for ts, buf in pcap:
            if t0 is None:
                t0 = ts
            try:
                eth = dpkt.ethernet.Ethernet(buf)
            except dpkt.dpkt.NeedData:
                continue
            ip = eth.data
            if not isinstance(ip, dpkt.ip.IP):
                continue
            udp = ip.data
            if not isinstance(udp, dpkt.udp.UDP):
                continue
            src_ip = ".".join(map(str, ip.src))
            dst_ip = ".".join(map(str, ip.dst))
            if udp.dport != 47808 and udp.sport != 47808:
                if not poller_ip or (src_ip != poller_ip and dst_ip != poller_ip):
                    continue
            bvlc, npdu, apdu, svc, bcast = parse_bacnet_udp(bytes(udp.data))
            records.append(
                PacketRecord(
                    ts=ts - t0,
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    src_port=udp.sport,
                    dst_port=udp.dport,
                    length=len(buf),
                    bvlc_function=bvlc,
                    npdu_control=npdu,
                    apdu_type=apdu,
                    service_choice=svc,
                    is_broadcast=bcast or dst_ip.endswith(".255"),
                )
            )
    return records


def read_pcap_tcpdump(pcap_path: Path, poller_ip: str | None = None) -> list[PacketRecord]:
    if not shutil.which("tcpdump"):
        raise SystemExit("tcpdump not found and dpkt unavailable")
    cmd = [
        "tcpdump",
        "-nn",
        "-tt",
        "-r",
        str(pcap_path),
        "udp",
        "port",
        "47808",
    ]
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    records: list[PacketRecord] = []
    pat = re.compile(
        r"^([\d.]+)\s+IP\s+(\S+)\.(\d+)\s+>\s+(\S+)\.(\d+):\s+UDP.*length\s+(\d+)"
    )
    t0 = None
    for line in out.splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        ts = float(m.group(1))
        if t0 is None:
            t0 = ts
        records.append(
            PacketRecord(
                ts=ts - (t0 or 0),
                src_ip=m.group(2),
                dst_ip=m.group(4),
                src_port=int(m.group(3)),
                dst_port=int(m.group(5)),
                length=int(m.group(6)),
            )
        )
    return records


def load_packets(pcap_path: Path, poller_ip: str | None = None) -> list[PacketRecord]:
    try:
        import dpkt  # noqa: F401

        return read_pcap_dpkt(pcap_path, poller_ip)
    except ImportError:
        print("WARN: dpkt not installed — using tcpdump metadata only (limited APDU decode)", file=sys.stderr)
        return read_pcap_tcpdump(pcap_path, poller_ip)


def peer_key(rec: PacketRecord, poller_ip: str) -> str | None:
    if rec.src_ip == poller_ip and rec.dst_port == 47808:
        return rec.dst_ip
    if rec.dst_ip == poller_ip and rec.src_port == 47808:
        return rec.src_ip
    return None


def analyze(
    pcap_path: Path,
    expectations: dict,
    duration_hint: float | None,
) -> AnalysisReport:
    bench = expectations["bench"]
    thresholds = expectations["thresholds"]
    devices = expectations["devices"]
    poller_ip = bench["poller_bind"]
    records = load_packets(pcap_path, poller_ip)

    duration = duration_hint or (records[-1].ts if records else 0.0)
    report = AnalysisReport(
        pcap=str(pcap_path),
        duration_secs=duration,
        total_packets=len(records),
        bacnet_packets=len(records),
    )

    if not records:
        report.errors.append("no UDP/47808 packets in capture")
        report.verdict = "FAIL"
        return report

    # Per-second rate
    by_sec: Counter[int] = Counter(int(r.ts) for r in records)
    peak_pps = max(by_sec.values()) if by_sec else 0
    report.stats["peak_packets_per_second"] = peak_pps
    if peak_pps > thresholds["max_packets_per_second"]:
        report.warnings.append(
            f"peak {peak_pps} pkt/s exceeds threshold {thresholds['max_packets_per_second']} (possible storm)"
        )
    else:
        report.passes.append(f"peak rate {peak_pps} pkt/s within threshold")

    # BVLC / service mix
    bvlc_counts: Counter[str] = Counter()
    service_counts: Counter[str] = Counter()
    whois_bcast = 0
    read_props = 0
    forwarded = 0
    foreign_reg = 0
    malformed_bvlc = 0

    for r in records:
        if r.bvlc_function is None:
            malformed_bvlc += 1
            continue
        bvlc_counts[hex(r.bvlc_function)] += 1
        if r.bvlc_function == BVLC_FORWARDED_NPDU:
            forwarded += 1
        if r.bvlc_function == BVLC_REGISTER_FOREIGN_DEVICE:
            foreign_reg += 1
        if r.service_choice == UNCONFIRMED_WHO_IS and r.is_broadcast:
            whois_bcast += 1
        if r.service_choice == CONFIRMED_READ_PROPERTY:
            read_props += 1
        if r.service_choice is not None:
            service_counts[str(r.service_choice)] += 1

    report.stats["bvlc_functions"] = dict(bvlc_counts)
    report.stats["service_choices"] = dict(service_counts)
    report.stats["forwarded_npdu_count"] = forwarded
    report.stats["read_property_count"] = read_props
    report.stats["whois_broadcast_count"] = whois_bcast
    report.stats["malformed_bvlc_count"] = malformed_bvlc

    if malformed_bvlc > len(records) * 0.05:
        report.errors.append(f"{malformed_bvlc} packets lack valid BACnet/IP BVLC header (>5%)")
    elif malformed_bvlc == 0:
        report.passes.append("all packets have BACnet/IP BVLC header (dpkt decode)")

    max_rfd = int(thresholds.get("max_register_foreign_device", 0))
    if foreign_reg > max_rfd:
        report.errors.append(f"{foreign_reg} Register-Foreign-Device messages (threshold {max_rfd})")

    whois_per_min = whois_bcast / max(duration / 60.0, 1.0)
    if whois_per_min > thresholds["max_whois_broadcast_per_minute"]:
        report.warnings.append(
            f"Who-Is broadcast rate {whois_per_min:.1f}/min exceeds {thresholds['max_whois_broadcast_per_minute']}"
        )
    else:
        report.passes.append(f"Who-Is broadcast rate {whois_per_min:.1f}/min acceptable")

    # Traffic per expected peer host
    to_peer: Counter[str] = Counter()
    from_peer: Counter[str] = Counter()
    for r in records:
        if r.src_ip == poller_ip and r.dst_port == 47808:
            to_peer[r.dst_ip] += 1
        if r.dst_ip == poller_ip and r.src_port == 47808:
            from_peer[r.src_ip] += 1

    report.stats["poller_tx_by_dst"] = dict(to_peer)
    report.stats["poller_rx_by_src"] = dict(from_peer)

    expected_hosts = {d["host"] for d in devices}
    for host in expected_hosts:
        tx = to_peer.get(host, 0)
        rx = from_peer.get(host, 0)
        if tx == 0:
            report.errors.append(f"no poller TX to expected host {host}")
        elif rx == 0:
            report.warnings.append(f"no poller RX from expected host {host} (device offline or one-way)")
        else:
            ratio = rx / tx if tx else 0
            report.stats[f"req_resp_ratio_{host}"] = round(ratio, 3)
            if 0.4 <= ratio <= 1.2:
                report.passes.append(f"{host} req/resp ratio {ratio:.2f} looks healthy")
            else:
                report.warnings.append(f"{host} req/resp ratio {ratio:.2f} outside 0.4–1.2")

    # Poll cadence: count poller->host bursts in 8-14s windows
    for dev in devices:
        host = dev["host"]
        interval = dev["interval_secs"]
        offset = dev.get("offset_secs", 0)
        n_points = len(dev.get("points", []))
        tx = to_peer.get(host, 0)
        expected_polls = max(0, (duration - offset) / interval) if duration > offset else 0
        expected_min_packets = expected_polls * n_points * 0.5  # request+response rough
        coverage = tx / expected_min_packets if expected_min_packets > 0 else 0
        report.stats[f"poll_coverage_{dev['instance']}"] = round(coverage, 3)
        if coverage >= thresholds["min_poll_coverage_ratio"]:
            report.passes.append(
                f"device {dev['instance']} ({host}) poll coverage {coverage:.0%} >= {thresholds['min_poll_coverage_ratio']:.0%}"
            )
        else:
            report.errors.append(
                f"device {dev['instance']} ({host}) poll coverage {coverage:.0%} < {thresholds['min_poll_coverage_ratio']:.0%} "
                f"(tx={tx}, expected_min≈{int(expected_min_packets)})"
            )
        if dev.get("routed") and forwarded == 0:
            report.warnings.append(
                f"device {dev['instance']} configured routed MSTP but no Forwarded-NPDU seen (decode may need dpkt)"
            )
        elif dev.get("routed") and forwarded > 0:
            report.passes.append(f"device {dev['instance']} routed traffic present ({forwarded} Forwarded-NPDU)")

    # Foreign :47808 sources (excluding poller + known peers)
    src_47808: Counter[str] = Counter()
    for r in records:
        if r.src_port == 47808:
            src_47808[r.src_ip] += 1
    allowed = {poller_ip, *expected_hosts}
    foreigners = {ip: c for ip, c in src_47808.items() if ip not in allowed}
    report.stats["foreign_47808_sources"] = foreigners
    if len(foreigners) > thresholds["max_foreign_47808_binders"]:
        report.errors.append(f"unexpected :47808 sources: {foreigners} (network conflict risk)")
    else:
        report.passes.append("no unexpected foreign :47808 binders")

    # Verdict
    if report.errors:
        report.verdict = "FAIL"
    elif report.warnings:
        report.verdict = "WARN"
    else:
        report.verdict = "PASS"
    return report


def write_markdown(report: AnalysisReport, out_path: Path) -> None:
    lines = [
        "# BACnet PCAP Analysis",
        "",
        f"- **PCAP:** `{report.pcap}`",
        f"- **Duration:** {report.duration_secs:.0f}s",
        f"- **Packets (UDP/47808):** {report.bacnet_packets}",
        f"- **Verdict:** **{report.verdict}**",
        "",
        "## Passes",
    ]
    lines.extend(f"- {p}" for p in report.passes) or lines.append("- (none)")
    lines.append("\n## Warnings")
    lines.extend(f"- {w}" for w in report.warnings) or lines.append("- (none)")
    lines.append("\n## Errors")
    lines.extend(f"- {e}" for e in report.errors) or lines.append("- (none)")
    lines.append("\n## Stats")
    lines.append("```json")
    lines.append(json.dumps(report.stats, indent=2))
    lines.append("```")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcap", required=True, type=Path)
    parser.add_argument("--expectations", type=Path, default=EXPECTATIONS)
    parser.add_argument("--duration", type=float, default=None, help="soak duration hint (seconds)")
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--md-out", type=Path, default=None)
    args = parser.parse_args()

    if not args.pcap.is_file():
        raise SystemExit(f"pcap not found: {args.pcap}")

    exp = load_expectations(args.expectations)
    report = analyze(args.pcap, exp, args.duration)

    print(json.dumps(report.to_dict(), indent=2))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.json_out}", file=sys.stderr)
    if args.md_out:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(report, args.md_out)
        print(f"wrote {args.md_out}", file=sys.stderr)

    return 0 if report.verdict == "PASS" else (1 if report.verdict == "FAIL" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
