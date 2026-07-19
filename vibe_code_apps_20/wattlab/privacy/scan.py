"""Repository privacy scanner and command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from .deny_list import PrivacyHit, scan_path

TEXT_EXTENSIONS = frozenset(
    {".py", ".json", ".yaml", ".yml", ".toml", ".md", ".csv", ".html", ".txt", ".sql", ".ipynb"}
)
FORBIDDEN_BINARY_EXTENSIONS = frozenset({".xlsx", ".xls", ".xlsm"})
EXCLUDED_DIRECTORIES = frozenset(
    {".venv", "__pycache__", ".pytest_cache", ".artifacts", "node_modules", ".git"}
)


def _walk(root: str | Path) -> Iterable[Path]:
    base = Path(root)
    for path in base.rglob("*"):
        if any(part in EXCLUDED_DIRECTORIES for part in path.relative_to(base).parts):
            continue
        if path.is_file():
            yield path


def iter_text_paths(root: str | Path) -> list[Path]:
    """Return tracked-like text files included in privacy scans."""

    return sorted(path for path in _walk(root) if path.suffix.casefold() in TEXT_EXTENSIONS)


def find_forbidden_binaries(
    root: str | Path,
    *,
    allowlist: Iterable[str | Path] = (),
) -> list[Path]:
    """Return prohibited workbook files not explicitly allowlisted."""

    base = Path(root).resolve()
    allowed = {
        (base / item).resolve() if not Path(item).is_absolute() else Path(item).resolve()
        for item in allowlist
    }
    return sorted(
        path
        for path in _walk(base)
        if path.suffix.casefold() in FORBIDDEN_BINARY_EXTENSIONS and path.resolve() not in allowed
    )


def scan_repository(
    root: str | Path,
    *,
    binary_allowlist: Iterable[str | Path] = (),
) -> tuple[list[PrivacyHit], list[Path]]:
    """Return text deny-list hits and prohibited workbook paths."""

    text_hits: list[PrivacyHit] = []
    for path in iter_text_paths(root):
        text_hits.extend(scan_path(path))
    return text_hits, find_forbidden_binaries(root, allowlist=binary_allowlist)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan WattLab for prohibited content")
    parser.add_argument("root", nargs="?", default=".", help="tree to scan")
    args = parser.parse_args(argv)

    text_hits, binaries = scan_repository(args.root)
    for hit in text_hits:
        print(f"{hit['path']}:{hit.get('line', '?')}: deny-list hash {hit['sha256']}")
    for path in binaries:
        print(f"{path}: forbidden workbook type")
    return 1 if text_hits or binaries else 0


if __name__ == "__main__":
    raise SystemExit(main())
