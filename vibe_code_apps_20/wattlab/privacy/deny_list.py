"""Hash-only deny-list scanning for proprietary identifiers and phrases."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import TypedDict


class PrivacyHit(TypedDict, total=False):
    """A deny-list match that does not disclose the matched text."""

    sha256: str
    token_index: int
    token_count: int
    path: str
    line: int


# Values are SHA-256 hashes of normalize_text(term). No restricted term is
# retained in plaintext. Token counts permit bounded n-gram matching.
DENY_HASHES_BY_TOKEN_COUNT: dict[int, frozenset[str]] = {
    1: frozenset(
        {
            "f2b941ca802f1357ccd9cf60d5c4f1bf20f8a2c542f796b1d9e1b3427f4e6748",
        }
    ),
    2: frozenset(
        {
            "46708a1f52346e511eda5553bad2c5a641a5f378cd372c3604a62ef6d5a22c7f",
            "ea55df224b35839ae8fcaaaa784ac83ec876fc154e24eef3b632ab69c5a5b480",
        }
    ),
    4: frozenset(
        {
            "b362a2fd6ef06ce78e14dd6cae73a6e1bbbb1d0d9a13120a5a19617cd96ca64d",
        }
    ),
    5: frozenset(
        {
            "7281e4bfaf38e8ac0311e109458a2904824212d1961ab2732d50f2be177a1756",
        }
    ),
    7: frozenset(
        {
            "27a56bf9099c51b105451443aac6f7d73d4d781752c33965b39f0e7f9e96f518",
        }
    ),
    9: frozenset(
        {
            "338f85d3309b045b494c436043019d43e21ffe7a3f8993d22109fb7b21202b3a",
        }
    ),
}


def normalize_text(text: str) -> str:
    """Return stable lowercase words with punctuation and spacing normalized."""

    folded = unicodedata.normalize("NFKC", text).casefold()
    alphanumeric_words = re.sub(r"[^a-z0-9]+", " ", folded)
    return " ".join(alphanumeric_words.split())


def sha256_norm(text: str) -> str:
    """Hash text after applying the scanner's normalization."""

    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def scan_text(text: str) -> list[PrivacyHit]:
    """Return non-disclosing deny-list hits in text."""

    tokens = normalize_text(text).split()
    hits: list[PrivacyHit] = []
    for token_count, forbidden_hashes in DENY_HASHES_BY_TOKEN_COUNT.items():
        for token_index in range(len(tokens) - token_count + 1):
            candidate = " ".join(tokens[token_index : token_index + token_count])
            candidate_hash = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
            if candidate_hash in forbidden_hashes:
                hits.append(
                    {
                        "sha256": candidate_hash,
                        "token_index": token_index,
                        "token_count": token_count,
                    }
                )
    return sorted(hits, key=lambda hit: (hit["token_index"], hit["token_count"]))


def scan_path(path: str | Path) -> list[PrivacyHit]:
    """Scan a UTF-8-compatible text file and annotate hits with its path."""

    source = Path(path)
    text = source.read_text(encoding="utf-8", errors="replace")
    return [{**hit, "path": str(source)} for hit in scan_text(text)]


def scan_tree(root: str | Path) -> list[PrivacyHit]:
    """Scan supported text files recursively under root."""

    from .scan import iter_text_paths

    hits: list[PrivacyHit] = []
    for path in iter_text_paths(root):
        hits.extend(scan_path(path))
    return hits
