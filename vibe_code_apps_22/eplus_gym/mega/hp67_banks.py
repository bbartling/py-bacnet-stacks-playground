"""Staged HP banks fallback when single-coil hp67 v2 still W2A-fails (Track B pattern)."""
from __future__ import annotations

import hashlib
from typing import Any

from eplus_gym.trackb_banks import (
    PUBLIC_LABEL,
    assert_reference_integrity,
    expand_complete_banks,
    nine_zone_plan,
    parse_eio_component_sizing,
    sizing_totals_from_eio,
)

from .hp67_two_pass import child_sha256


def eio_totals_for_hp67(eio_text: str) -> dict[str, dict[str, Any]]:
    parsed = parse_eio_component_sizing(eio_text)
    return sizing_totals_from_eio(parsed)


def build_hp67_banks_child(
    pass1_autosize_text: str,
    *,
    eio_text: str,
    sensitivity: str = "base",
) -> tuple[str, dict[str, Any]]:
    """Replace each zone W2A unit with staged banks sized from Pass 1 EIO totals."""
    totals = eio_totals_for_hp67(eio_text)
    plan = nine_zone_plan(sensitivity=sensitivity)
    expanded = expand_complete_banks(pass1_autosize_text, plan, sizing_totals=totals)
    integrity = assert_reference_integrity(expanded, plan)
    meta = {
        "schema": "vibe22.hp67.banks_fallback.v1",
        "public_label": PUBLIC_LABEL,
        "sensitivity": sensitivity,
        "nine_zone_plan": plan,
        "reference_integrity": integrity,
        "sizing_totals_provenance": "pass1_eio",
        "child_idf_sha256": child_sha256(expanded),
        "not_threshold_manipulation": True,
    }
    return expanded, meta
