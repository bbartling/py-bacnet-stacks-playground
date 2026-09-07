#!/usr/bin/env python3
"""Fail-closed Vibe13 wiring manifest contract (no network, no tty open)."""
from __future__ import annotations

import hashlib
import json
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

# Controller-owned allowlist — inventory cannot override these IPs.
TRUSTED_HOSTS: dict[str, str] = {
    "workerpi1": "192.168.204.59",
    "workerpi2": "192.168.204.60",
}

# CI / docs-only fixture IPs (RFC5737) — never LAN.
CI_DOC_HOSTS: dict[str, str] = {
    "workerpi1": "198.51.100.59",
    "workerpi2": "198.51.100.60",
}

ALLOWED_PROFILES = frozenset(
    {
        "raw-smoke",
        "raw-gate",
        "raw-wire",  # alias → raw-smoke
        "mstp-smoke",
        "mstp-gate",
        "mstp-soak",
    }
)
ALLOWED_PAIRS = frozenset({"cb"})
ALLOWED_ORIENTATIONS = frozenset({"workerpi1-server", "workerpi2-server"})
BIAS_STATUS = frozenset({"verified", "unknown", "not_measured"})

# Two ~120Ω onboard terminations → ~60Ω; documented band with override.
# Operator 2026-09-07 measured combined ~71Ω (127Ω each) — allow slight meter/lead headroom.
COMBINED_OHM_MIN = 55.0
COMBINED_OHM_MAX = 75.0
INDIVIDUAL_OHM_MIN = 100.0
INDIVIDUAL_OHM_MAX = 140.0

SCHEMA = "vibe13_wiring_v2"
UPSTREAM_SHA = "af4e88680c51eb4da64dac47f0540a35bf184732"

DURATION_BOUNDS_SECS = {
    "raw-smoke": (30, 900),
    "raw-gate": (300, 7200),
    "raw-wire": (30, 900),
    "mstp-smoke": (30, 600),
    "mstp-gate": (300, 3600),
    "mstp-soak": (600, 7200),
}


def normalize_profile(profile: str) -> str:
    p = (profile or "").strip()
    if p == "raw-wire":
        return "raw-smoke"
    if p not in ALLOWED_PROFILES:
        raise ValueError(
            f"invalid profile {profile!r}; allowed={sorted(ALLOWED_PROFILES - {'raw-wire'})}"
        )
    return p


def parse_duration_to_secs(raw: str | None, profile: str) -> int:
    """Parse Ns/Nm/Nh or bare seconds; enforce profile bounds."""
    lo, hi = DURATION_BOUNDS_SECS[normalize_profile(profile)]
    if raw is None or raw == "":
        defaults = {
            "raw-smoke": 120,
            "raw-gate": 1800,
            "mstp-smoke": 120,
            "mstp-gate": 900,
            "mstp-soak": 3600,
        }
        return defaults[normalize_profile(profile)]
    s = str(raw).strip().lower()
    if s.endswith("h"):
        secs = int(float(s[:-1]) * 3600)
    elif s.endswith("m"):
        secs = int(float(s[:-1]) * 60)
    elif s.endswith("s"):
        secs = int(float(s[:-1]))
    else:
        secs = int(s)
    if secs < lo or secs > hi:
        raise ValueError(f"duration {secs}s out of bounds [{lo},{hi}] for {profile}")
    return secs


def assert_trusted_host(hostname: str, ansible_host: str, *, allow_ci_doc: bool = False) -> None:
    expected = TRUSTED_HOSTS.get(hostname)
    if expected is None:
        raise ValueError(f"unknown hostname {hostname!r}")
    if ansible_host == expected:
        return
    if allow_ci_doc and ansible_host == CI_DOC_HOSTS.get(hostname):
        return
    raise ValueError(
        f"host {hostname} ansible_host={ansible_host!r} not in controller allowlist "
        f"(expected {expected}"
        + (f" or CI {CI_DOC_HOSTS[hostname]}" if allow_ci_doc else "")
        + ")"
    )


def inventory_digest(inventory_bytes: bytes) -> str:
    return hashlib.sha256(inventory_bytes).hexdigest()


def _require_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{name} must be numeric ohms, got {value!r}")
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError as e:
            raise ValueError(f"{name} must be numeric ohms, got {value!r}") from e
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric ohms, got {value!r}")
    return float(value)


def validate_resistance_fields(
    data: dict[str, Any], *, allow_override: bool
) -> None:
    r1 = _require_number(
        "workerpi1_unpowered_ab_ohm", data.get("workerpi1_unpowered_ab_ohm")
    )
    r2 = _require_number(
        "workerpi2_unpowered_ab_ohm", data.get("workerpi2_unpowered_ab_ohm")
    )
    combined = _require_number(
        "combined_unpowered_ab_ohm", data.get("combined_unpowered_ab_ohm")
    )
    if not allow_override:
        if not (INDIVIDUAL_OHM_MIN <= r1 <= INDIVIDUAL_OHM_MAX):
            raise ValueError(
                f"workerpi1_unpowered_ab_ohm={r1} outside [{INDIVIDUAL_OHM_MIN},{INDIVIDUAL_OHM_MAX}] "
                f"(use resistance_override_reason for documented exception)"
            )
        if not (INDIVIDUAL_OHM_MIN <= r2 <= INDIVIDUAL_OHM_MAX):
            raise ValueError(
                f"workerpi2_unpowered_ab_ohm={r2} outside [{INDIVIDUAL_OHM_MIN},{INDIVIDUAL_OHM_MAX}]"
            )
        if not (COMBINED_OHM_MIN <= combined <= COMBINED_OHM_MAX):
            raise ValueError(
                f"combined_unpowered_ab_ohm={combined} outside [{COMBINED_OHM_MIN},{COMBINED_OHM_MAX}]"
            )
    else:
        reason = data.get("resistance_override_reason")
        if not reason or not str(reason).strip():
            raise ValueError("resistance_override_reason required when override is set")


def build_manifest(
    *,
    inventory_text: str,
    project_sha: str,
    upstream_sha: str,
    pair: str,
    orientation: str,
    profile: str,
    baud: int,
    max_master: int,
    max_info_frames: int,
    hosts: dict[str, dict[str, Any]],
    workerpi1_ohm: float,
    workerpi2_ohm: float,
    combined_ohm: float,
    bias_status: str,
    polarity_confirmed: bool,
    no_vcc_confirmed: bool,
    resistance_override_reason: str | None = None,
    max_age_hours: int = 8,
) -> dict[str, Any]:
    if pair not in ALLOWED_PAIRS:
        raise ValueError(f"pair must be one of {sorted(ALLOWED_PAIRS)}")
    if orientation not in ALLOWED_ORIENTATIONS:
        raise ValueError(f"orientation must be one of {sorted(ALLOWED_ORIENTATIONS)}")
    if bias_status not in BIAS_STATUS:
        raise ValueError(f"bias_status must be one of {sorted(BIAS_STATUS)}")
    if not polarity_confirmed or not no_vcc_confirmed:
        raise ValueError("polarity_confirmed and no_vcc_confirmed must be true")
    profile = normalize_profile(profile)
    if len(project_sha) != 40:
        raise ValueError("controller_project_sha must be 40-char git SHA")
    if upstream_sha != UPSTREAM_SHA:
        raise ValueError(f"upstream_sha must remain frozen {UPSTREAM_SHA}")

    for hn, meta in hosts.items():
        ah = str(meta["ansible_host"])
        # Allow CI fixture IPs only when they match CI_DOC_HOSTS (never LAN).
        assert_trusted_host(
            hn, ah, allow_ci_doc=ah in CI_DOC_HOSTS.values()
        )

    data = {
        "workerpi1_unpowered_ab_ohm": workerpi1_ohm,
        "workerpi2_unpowered_ab_ohm": workerpi2_ohm,
        "combined_unpowered_ab_ohm": combined_ohm,
        "resistance_override_reason": resistance_override_reason,
    }
    validate_resistance_fields(data, allow_override=bool(resistance_override_reason))

    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=max_age_hours)
    nonce = secrets.token_hex(16)

    # Derive roles from orientation without changing physical host identity.
    if orientation == "workerpi1-server":
        role_map = {"workerpi1": "server", "workerpi2": "probe"}
    else:
        role_map = {"workerpi1": "probe", "workerpi2": "server"}

    out_hosts: dict[str, Any] = {}
    for hn, meta in hosts.items():
        out_hosts[hn] = {
            **meta,
            "role": role_map[hn],
        }

    return {
        "schema": SCHEMA,
        "schema_version": 2,
        "approved_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_utc": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "max_age_hours": max_age_hours,
        "nonce": nonce,
        "nonce_consumed": False,
        "controller_project_sha": project_sha.lower(),
        "upstream_sha": upstream_sha.lower(),
        "inventory_digest_sha256": inventory_digest(inventory_text.encode("utf-8")),
        "pair": pair,
        "orientation": orientation,
        "topology": "isolated_direct_wire",
        "polarity": "A+↔A+, B-↔B-, GND/REF↔GND/REF",
        "polarity_confirmed": True,
        "no_vcc_confirmed": True,
        "bias_status": bias_status,
        "workerpi1_unpowered_ab_ohm": float(workerpi1_ohm),
        "workerpi2_unpowered_ab_ohm": float(workerpi2_ohm),
        "combined_unpowered_ab_ohm": float(combined_ohm),
        "resistance_override_reason": resistance_override_reason,
        "operator_confirmed": True,
        "requested_profile": profile,
        "allowed_profiles": sorted(ALLOWED_PROFILES - {"raw-wire"}),
        "baud": int(baud),
        "max_master": int(max_master),
        "max_info_frames": int(max_info_frames),
        "hosts": out_hosts,
        "notes": "Isolated C↔B only; tower Waveshare C and FEC out of scope. TX still off until run --allow-tx.",
    }


def validate_manifest_for_run(
    wiring: dict[str, Any],
    *,
    inventory_text: str,
    project_sha: str,
    profile: str,
    pair: str,
    orientation: str,
    live_hosts: dict[str, dict[str, Any]],
) -> None:
    if wiring.get("schema") not in (SCHEMA, "vibe13_wiring_v1"):
        # Accept v1 only if migrating? Plan wants typed v2 fail-closed — reject v1.
        if wiring.get("schema") != SCHEMA:
            raise ValueError(
                f"unsupported wiring schema {wiring.get('schema')!r}; re-run confirm-wiring"
            )
    if not wiring.get("operator_confirmed"):
        raise ValueError("operator_confirmed is not true")
    if wiring.get("nonce_consumed"):
        raise ValueError("wiring nonce already consumed; re-run confirm-wiring")
    nonce = wiring.get("nonce")
    if not nonce or not isinstance(nonce, str) or len(nonce) < 16:
        raise ValueError("wiring nonce missing/invalid; re-run confirm-wiring")

    expires = wiring.get("expires_utc") or ""
    approved = wiring.get("approved_utc") or ""
    if not expires and approved:
        # derive from max_age if old field only
        max_h = int(wiring.get("max_age_hours") or 8)
        ts = approved.replace("Z", "+00:00")
        t = datetime.fromisoformat(ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        exp = t + timedelta(hours=max_h)
    else:
        ts = str(expires).replace("Z", "+00:00")
        exp = datetime.fromisoformat(ts)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if now > exp.astimezone(timezone.utc):
        raise ValueError(f"wiring expired at {expires}")

    if wiring.get("controller_project_sha", "").lower() != project_sha.lower():
        raise ValueError("controller_project_sha mismatch vs current HEAD")
    if wiring.get("upstream_sha", UPSTREAM_SHA).lower() != UPSTREAM_SHA.lower():
        raise ValueError("upstream_sha mismatch vs frozen pin")
    digest = inventory_digest(inventory_text.encode("utf-8"))
    if wiring.get("inventory_digest_sha256") != digest:
        raise ValueError("inventory_digest_sha256 mismatch; re-run confirm-wiring")

    profile_n = normalize_profile(profile)
    req = normalize_profile(str(wiring.get("requested_profile") or profile_n))
    allowed = set(wiring.get("allowed_profiles") or [req])
    if profile_n not in allowed and profile_n != req:
        raise ValueError(f"profile {profile_n} not in wiring allowed_profiles={sorted(allowed)}")
    if pair != wiring.get("pair"):
        raise ValueError(f"pair {pair!r} != wiring pair {wiring.get('pair')!r}")
    if orientation != wiring.get("orientation"):
        raise ValueError(
            f"orientation {orientation!r} != wiring {wiring.get('orientation')!r}"
        )
    if wiring.get("topology") != "isolated_direct_wire":
        raise ValueError("topology must be isolated_direct_wire")

    validate_resistance_fields(wiring, allow_override=bool(wiring.get("resistance_override_reason")))
    bias = wiring.get("bias_status")
    if bias not in BIAS_STATUS:
        raise ValueError(f"invalid bias_status {bias!r}")

    for hn, live in live_hosts.items():
        wh = wiring.get("hosts", {}).get(hn) or {}
        assert_trusted_host(hn, str(live.get("ansible_host") or wh.get("ansible_host")))
        for key, wkey in (
            ("lab_serial_by_id", "serial_by_id"),
            ("lab_adapter_model", "adapter_model"),
            ("lab_adapter_vid_pid", "vid_pid"),
        ):
            if str(live.get(key)) != str(wh.get(wkey)):
                raise ValueError(f"{hn} {wkey} mismatch wiring vs live inventory")
        if int(live.get("lab_mstp_mac")) != int(wh.get("mac")):
            raise ValueError(f"{hn} mac mismatch")
        if int(live.get("lab_device_instance")) == 123001:
            raise ValueError(f"{hn} collides with tower device instance 123001")


def consume_nonce(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("wiring file is not a mapping")
    if data.get("nonce_consumed"):
        raise ValueError("nonce already consumed")
    data["nonce_consumed"] = True
    data["nonce_consumed_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Atomic-ish replace
    tmp = path.with_suffix(".yml.tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    tmp.replace(path)


def roles_for_orientation(orientation: str) -> dict[str, str]:
    if orientation == "workerpi1-server":
        return {"workerpi1": "server", "workerpi2": "probe"}
    if orientation == "workerpi2-server":
        return {"workerpi1": "probe", "workerpi2": "server"}
    raise ValueError(f"bad orientation {orientation!r}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "usage: wiring_contract.py check-host|normalize-profile|parse-duration|"
            "consume-nonce|validate-run|build-manifest-json ...",
            file=sys.stderr,
        )
        return 2
    cmd = argv[1]
    try:
        if cmd == "check-host":
            if len(argv) < 4:
                return 2
            allow_ci = "--ci-doc" in argv
            assert_trusted_host(argv[2], argv[3], allow_ci_doc=allow_ci)
            print("ok")
        elif cmd == "normalize-profile":
            print(normalize_profile(argv[2]))
        elif cmd == "parse-duration":
            print(parse_duration_to_secs(argv[3] if len(argv) > 3 else None, argv[2]))
        elif cmd == "consume-nonce":
            consume_nonce(Path(argv[2]))
            print("consumed")
        elif cmd == "validate-run":
            # wiring.yml inventory.yml project_sha profile pair orientation live_hosts.json
            if len(argv) != 9:
                print(
                    "usage: validate-run <wiring> <inv> <sha> <profile> <pair> <orientation> <live.json>",
                    file=sys.stderr,
                )
                return 2
            wiring = yaml.safe_load(Path(argv[2]).read_text(encoding="utf-8"))
            inv = Path(argv[3]).read_text(encoding="utf-8")
            live = json.loads(Path(argv[8]).read_text(encoding="utf-8"))
            validate_manifest_for_run(
                wiring,
                inventory_text=inv,
                project_sha=argv[4],
                profile=argv[5],
                pair=argv[6],
                orientation=argv[7],
                live_hosts=live,
            )
            print("ok")
        elif cmd == "roles-for-orientation":
            print(json.dumps(roles_for_orientation(argv[2])))
        elif cmd == "write-manifest":
            # write-manifest <inventory.yml> <out.yml> <params.json>
            if len(argv) != 5:
                print(
                    "usage: write-manifest <inventory.yml> <out.yml> <params.json>",
                    file=sys.stderr,
                )
                return 2
            inv_path = Path(argv[2])
            out_path = Path(argv[3])
            params = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
            inv_text = inv_path.read_text(encoding="utf-8")
            inv = yaml.safe_load(inv_text)
            hosts_block = inv["all"]["children"]["vibe13_pi_lab"]["hosts"]
            gvars = inv["all"]["children"]["vibe13_pi_lab"].get("vars") or {}
            hosts = {}
            for hn in ("workerpi1", "workerpi2"):
                h = hosts_block[hn]
                hosts[hn] = {
                    "ansible_host": str(h["ansible_host"]),
                    "adapter_model": h["lab_adapter_model"],
                    "vid_pid": h["lab_adapter_vid_pid"],
                    "serial_short": h.get("lab_adapter_serial_short") or "",
                    "serial_by_id": h["lab_serial_by_id"],
                    "mac": int(h["lab_mstp_mac"]),
                    "device_instance": int(h["lab_device_instance"]),
                }
            # Reject OPERATOR_MEASURE and non-numeric strings early.
            for key in (
                "workerpi1_ohm",
                "workerpi2_ohm",
                "combined_ohm",
            ):
                v = params.get(key)
                if isinstance(v, str) and "OPERATOR" in v.upper():
                    raise ValueError(f"{key} rejects OPERATOR_MEASURE placeholders")
            manifest = build_manifest(
                inventory_text=inv_text,
                project_sha=str(params["project_sha"]),
                upstream_sha=str(params.get("upstream_sha") or UPSTREAM_SHA),
                pair=str(params["pair"]),
                orientation=str(params["orientation"]),
                profile=str(params["profile"]),
                baud=int(params.get("baud") or gvars.get("lab_baud") or 38400),
                max_master=int(params.get("max_master") or gvars.get("lab_max_master") or 2),
                max_info_frames=int(
                    params.get("max_info_frames") or gvars.get("lab_max_info_frames") or 1
                ),
                hosts=hosts,
                workerpi1_ohm=params["workerpi1_ohm"],
                workerpi2_ohm=params["workerpi2_ohm"],
                combined_ohm=params["combined_ohm"],
                bias_status=str(params["bias_status"]),
                polarity_confirmed=bool(params.get("polarity_confirmed")),
                no_vcc_confirmed=bool(params.get("no_vcc_confirmed")),
                resistance_override_reason=params.get("resistance_override_reason"),
                max_age_hours=int(params.get("max_age_hours") or 8),
            )
            tmp = out_path.with_suffix(".yml.tmp")
            tmp.write_text(
                "# Generated by confirm-wiring (vibe13_wiring_v2) — not a secret.\n"
                + yaml.safe_dump(manifest, sort_keys=False),
                encoding="utf-8",
            )
            tmp.replace(out_path)
            print(out_path)
        else:
            print(f"unknown cmd {cmd}", file=sys.stderr)
            return 2
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
