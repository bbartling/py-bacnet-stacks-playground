"""Immutable A04 identity and candidate filename contract."""
from __future__ import annotations

import math
from pathlib import Path

A04_IDF_NAME = "lakeside_w2a_a04_dual_champion.idf"
A04_SHA_CRLF = "212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683"
A04_SHA_LF = "080ab87797c78df0c8efb257a52bba97f550ee628ec4bd1333801b2e104b21eb"
A04_SHA_ALLOWED = frozenset({A04_SHA_CRLF, A04_SHA_LF})
CAPMULT_LO = 1.0
CAPMULT_HI = 80.0
INTERNALMASS_LO = 0.0
INTERNALMASS_HI = 5000.0


def is_a04_idf_filename(name: str) -> bool:
    """Champion A04, staged A04 copies, or separately versioned A04-v2 children.

    Prefixed names such as ``unreviewed_lakeside_w2a_a04_dual_champion.idf`` are rejected.
    """
    n = Path(name).name
    if n == A04_IDF_NAME or n == f"staged_{A04_IDF_NAME}":
        return True
    base = n[7:] if n.startswith("staged_") else n
    return base.startswith("lakeside_w2a_a04v2_") and base.endswith(".idf")


def is_canonical_a04_idf_filename(name: str) -> bool:
    n = Path(name).name
    return n in {A04_IDF_NAME, f"staged_{A04_IDF_NAME}"}


def assert_finite_in_range(value: float, *, lo: float, hi: float, name: str) -> float:
    x = float(value)
    if not math.isfinite(x) or x < lo or x > hi:
        raise ValueError(f"{name}={value!r} is outside [{lo}, {hi}]")
    return x
