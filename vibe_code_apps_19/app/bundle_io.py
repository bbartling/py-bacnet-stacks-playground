"""Parquet-first table writers for the engineering bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

try:
    import pyarrow  # noqa: F401

    HAS_PYARROW = True
except Exception:  # pragma: no cover
    HAS_PYARROW = False


def write_canonical_table(
    df: pd.DataFrame,
    path_without_suffix: Path,
    *,
    also_csv: bool = True,
) -> dict[str, Path]:
    """Write Parquet when possible; keep a small CSV twin during migration."""
    written: dict[str, Path] = {}
    stem = Path(path_without_suffix)
    stem.parent.mkdir(parents=True, exist_ok=True)
    if HAS_PYARROW:
        pq = stem.with_suffix(".parquet")
        df.to_parquet(pq, index=False)
        written["parquet"] = pq
    if also_csv or not HAS_PYARROW:
        csv = stem.with_suffix(".csv")
        df.to_csv(csv, index=False)
        written["csv"] = csv
    return written


def dumps_json_safe(payload: Any, *, indent: int = 2) -> str:
    import json

    from open_fdd.rules.evidence import json_safe

    text = json.dumps(json_safe(payload), indent=indent, ensure_ascii=True)
    # Do not use assert_no_pandas_repr on whole documents: README/how_to_use
    # strings legitimately contain "...". Flag pandas-specific leaks only.
    if "dtype:" in text or "Length:" in text:
        raise ValueError("pandas repr leaked into JSON evidence")
    return text
