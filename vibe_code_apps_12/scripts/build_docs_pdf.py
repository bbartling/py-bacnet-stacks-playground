#!/usr/bin/env python3
"""
Build a single PDF from Vibe12 documentation (docs/ + manifest.yaml).

  python3 scripts/build_docs_pdf.py
  python3 scripts/build_docs_pdf.py -o pdf/vibe12-edge-fdd-guide.pdf

Requirements: pandoc, pyyaml; PDF via weasyprint (pip install weasyprint) or pdflatex.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_KRAMDOWN_IAL_RE = re.compile(r"\{:[^}\n]*\}\s*")

try:
    import yaml
except ImportError:
    yaml = None

SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = SCRIPT_DIR.parent
DOCS_DIR = APP_ROOT / "docs"
PDF_DIR = APP_ROOT / "pdf"
BUILD_DIR = DOCS_DIR / "_build"
MANIFEST = DOCS_DIR / "manifest.yaml"
DEFAULT_OUTPUT = PDF_DIR / "vibe12-edge-fdd-guide.pdf"


def parse_front_matter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, min(len(lines), 40)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    yaml_block = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :]).lstrip()
    try:
        fm = yaml.safe_load(yaml_block) if yaml_block.strip() else {}
    except Exception:
        fm = {}
    return (fm or {}), body


def strip_kramdown_ial(text: str) -> str:
    return _KRAMDOWN_IAL_RE.sub("", text)


def load_manifest() -> list[tuple[Path, str | None]]:
    """Return [(path, title_override), ...] in order."""
    if not MANIFEST.is_file() or yaml is None:
        return []
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    out: list[tuple[Path, str | None]] = []
    for entry in data.get("pages", []):
        if isinstance(entry, str):
            out.append((APP_ROOT / entry, None))
        elif isinstance(entry, dict) and entry.get("path"):
            out.append((APP_ROOT / entry["path"], entry.get("title")))
    return out


def collect_md_files(docs_dir: Path) -> list[Path]:
    out: list[Path] = []
    for f in sorted(docs_dir.rglob("*.md")):
        if f.name == "404.md" or "_build" in f.parts or f.name == "manifest.yaml":
            continue
        out.append(f)
    return out


def section_order_key(path: Path, fm: dict, title_to_nav: dict[str, int]) -> tuple[int, int, str]:
    parent = fm.get("parent") or ""
    nav = fm.get("nav_order")
    if nav is None:
        nav = 999
    try:
        nav = int(nav)
    except (TypeError, ValueError):
        nav = 999
    section_nav = title_to_nav.get(parent, 999) if parent else nav
    return (section_nav, nav, str(path))


def build_title_to_nav(files: list[Path]) -> dict[str, int]:
    title_to_nav: dict[str, int] = {}
    for path in files:
        fm, _ = parse_front_matter(path)
        title = fm.get("title")
        nav = fm.get("nav_order")
        if title and nav is not None:
            try:
                title_to_nav[title] = int(nav)
            except (TypeError, ValueError):
                pass
    return title_to_nav


def resolve_pages(manifest_pages: list[tuple[Path, str | None]]) -> list[tuple[Path, str | None]]:
    if manifest_pages:
        return manifest_pages
    files = collect_md_files(DOCS_DIR)
    title_to_nav = build_title_to_nav(files)
    sorted_files = sorted(
        files,
        key=lambda p: section_order_key(p, parse_front_matter(p)[0], title_to_nav),
    )
    return [(p, None) for p in sorted_files]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Vibe12 docs PDF (Pandoc).")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--keep-md", action="store_true")
    parser.add_argument(
        "--pdf-engine",
        choices=["weasyprint", "pdflatex", "xelatex"],
        default="weasyprint",
    )
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()

    if yaml is None:
        print("PyYAML required: pip install pyyaml", file=sys.stderr)
        return 1

    pages = resolve_pages(load_manifest())
    if not pages:
        print(f"No pages found under {DOCS_DIR}", file=sys.stderr)
        return 1

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    combined_path = BUILD_DIR / "combined.md"
    now = datetime.now()
    build_date = now.strftime(f"%B {now.day}, %Y")

    parts: list[str] = [
        "% Vibe12 — Edge BACnet & Cloud FDD\n",
        "% py-bacnet-stacks-playground / vibe_code_apps_12\n",
        f"% {build_date}\n\n",
        f"*Generated {build_date}*\n\n",
        "---\n\n",
    ]

    for path, title_override in pages:
        if not path.is_file():
            print(f"Skip missing: {path}", file=sys.stderr)
            continue
        fm, body = parse_front_matter(path)
        if fm.get("nav_exclude"):
            continue
        title = title_override or fm.get("title") or path.stem.replace("-", " ").title()
        parts.append(f"# {title}\n\n")
        parts.append(strip_kramdown_ial(body))
        if not body.endswith("\n"):
            parts.append("\n")
        parts.append("\n\n")

    combined_md = "".join(parts)
    combined_path.write_text(combined_md, encoding="utf-8")
    print(f"Wrote {len(pages)} sections to {combined_path}")

    txt_output = args.output.with_suffix(".txt")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    txt_output.write_text(combined_md, encoding="utf-8")
    print(f"Wrote {txt_output}")

    if args.no_pdf:
        return 0

    cmd = [
        "pandoc",
        str(combined_path),
        "-o",
        str(args.output),
        "--toc",
        "--number-sections",
        f"--pdf-engine={args.pdf_engine}",
        "-V",
        "documentclass=article",
        "-V",
        "papersize=letter",
        "-V",
        "geometry:margin=1in",
        "-V",
        f"date={build_date}",
    ]
    print(f"Running: {' '.join(cmd)}")
    env = os.environ.copy()
    py_bin = str(Path(sys.executable).resolve().parent)
    if py_bin:
        env["PATH"] = py_bin + os.pathsep + env.get("PATH", "")
    try:
        subprocess.run(cmd, check=True, cwd=APP_ROOT, env=env)
    except FileNotFoundError:
        print("pandoc not found: https://pandoc.org/installing.html", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"Pandoc failed (engine={args.pdf_engine})", file=sys.stderr)
        return e.returncode

    print(f"PDF: {args.output}")
    if not args.keep_md:
        combined_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
