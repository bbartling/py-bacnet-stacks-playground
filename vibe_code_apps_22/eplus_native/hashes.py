"""SHA-256 helpers and champion pin checks."""
from __future__ import annotations

import hashlib
from pathlib import Path

from eplus_native import EXPECTED_EPW_SHA256, EXPECTED_IDF_SHA256


def sha256_file(path: Path | str) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def assert_champion_hashes(
    idf: Path | str,
    epw: Path | str,
    *,
    expected_idf: str = EXPECTED_IDF_SHA256,
    expected_epw: str = EXPECTED_EPW_SHA256,
    allow_staged: bool = False,
) -> dict[str, str]:
    """Fail if EPW hash mismatches. IDF must match champion unless allow_staged."""
    idf_h = sha256_file(idf)
    epw_h = sha256_file(epw)
    if epw_h != expected_epw.upper():
        raise ValueError(
            f"EPW hash mismatch: got {epw_h}, expected {expected_epw}. Stale weather pin."
        )
    if not allow_staged and idf_h != expected_idf.upper():
        raise ValueError(
            f"IDF hash mismatch: got {idf_h}, expected {expected_idf}. "
            "Use staged repair path with allow_staged=True after Phase 1."
        )
    return {"idf_sha256": idf_h, "epw_sha256": epw_h}
