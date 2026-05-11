#!/usr/bin/env python3
"""
Build a single human-readable PDF (and matching .txt) from bas_build_spec Markdown.

Collects curated orchestration docs in reading order: orientation, memory,
checkpoints, acceptance criteria, product spec, skills, BACnet lab notes, and
cron operator docs. Optional full BACnet reference corpus via --include-bacnet-reference.

Outputs (default):
  bas_build_spec/pdf/bas-build-spec.pdf
  bas_build_spec/pdf/bas-build-spec.txt

Requirements:
  - pandoc (https://pandoc.org/) — portable copy may live in tools/bin/pandoc
  - PyYAML (pip install pyyaml)
  - For PDF (first available): typst in tools/bin/typst, or weasyprint on PATH, or LaTeX

When WeasyPrint is installed only inside a virtualenv, this script prepends the
current Python's bin directory to PATH for the Pandoc subprocess.

Usage:
  python3 tools/build_bas_spec_pdf.py
  python3 tools/build_bas_spec_pdf.py -o pdf/bas-build-spec-preview.pdf
  python3 tools/build_bas_spec_pdf.py --no-pdf
  python3 tools/build_bas_spec_pdf.py --include-bacnet-reference
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
SPEC_ROOT = SCRIPT_DIR.parent
TOOLS_BIN = SCRIPT_DIR / "bin"
PDF_DIR = SPEC_ROOT / "pdf"
BUILD_DIR = SPEC_ROOT / "_build" / "docs"
DEFAULT_OUTPUT = PDF_DIR / "bas-build-spec.pdf"

# Human reading order (paths relative to bas_build_spec/).
CORE_MANIFEST: list[str] = [
    "AGENTS.md",
    "MEMORY.md",
    "BUILD_CHECKPOINTS.md",
    "acceptance_criteria.md",
    "spec.md",
    "skills/README.md",
    "skills/GUARDRAILS.md",
    "memory/README.md",
    "memory/architecture/README.md",
    "memory/architecture/working-divergence.md",
    "memory/integrations/bacnet.md",
    "bacnet_scripts_example/README.md",
    "cron_codex/README.md",
    "cron_codex/CHEATSHEET.md",
    "cron_codex/TUTORIAL.md",
    "cron_codex/state/next_directions.md",
]


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


def title_for(path: Path, fm: dict) -> str:
    if fm.get("title"):
        return str(fm["title"])
    if path.stem == "SKILL":
        return path.parent.name.replace("-", " ").title()
    return path.stem.replace("-", " ").replace("_", " ").title()


def collect_skill_paths() -> list[Path]:
    skills_root = SPEC_ROOT / "skills"
    paths: list[Path] = []
    for skill_md in sorted(skills_root.glob("*/SKILL.md")):
        paths.append(skill_md)
    for ref_md in sorted(skills_root.glob("*/references/*.md")):
        paths.append(ref_md)
    return paths


def resolve_manifest(include_bacnet_reference: bool) -> list[Path]:
    ordered: list[Path] = []
    seen: set[Path] = set()
    for rel in CORE_MANIFEST:
        path = SPEC_ROOT / rel
        if not path.is_file():
            print(f"WARN: missing manifest entry: {rel}", file=sys.stderr)
            continue
        canon = path.resolve()
        if canon in seen:
            continue
        seen.add(canon)
        ordered.append(path)
    for path in collect_skill_paths():
        canon = path.resolve()
        if canon in seen:
            continue
        seen.add(canon)
        ordered.append(path)
    if include_bacnet_reference:
        bacnet_ref = SPEC_ROOT / "bacnet_scripts.md"
        if bacnet_ref.is_file():
            ordered.append(bacnet_ref)
    return ordered


def pandoc_path() -> str:
    bundled = TOOLS_BIN / "pandoc"
    if bundled.is_file():
        return str(bundled)
    return "pandoc"


def default_pdf_engine() -> str:
    if (TOOLS_BIN / "typst").is_file():
        return "typst"
    return "weasyprint"


def pdf_engine_arg(engine: str) -> str:
    if engine == "typst":
        bundled = TOOLS_BIN / "typst"
        if bundled.is_file():
            return f"--pdf-engine={bundled}"
    return f"--pdf-engine={engine}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build bas_build_spec Markdown into a single PDF via Pandoc."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output PDF path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--keep-md",
        action="store_true",
        help="Keep combined Markdown in bas_build_spec/_build/docs/combined.md",
    )
    parser.add_argument(
        "--pdf-engine",
        choices=["typst", "weasyprint", "pdflatex", "xelatex"],
        default=None,
        help="Pandoc PDF engine (default: typst in tools/bin if present, else weasyprint)",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Only write combined.md and .txt, do not run Pandoc",
    )
    parser.add_argument(
        "--include-bacnet-reference",
        action="store_true",
        help="Append bacnet_scripts.md (large embedded Python reference corpus)",
    )
    args = parser.parse_args()

    if yaml is None:
        print("PyYAML is required. pip install pyyaml", file=sys.stderr)
        return 1

    files = resolve_manifest(args.include_bacnet_reference)
    if not files:
        print("No Markdown files found for manifest.", file=sys.stderr)
        return 1

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    combined_path = BUILD_DIR / "combined.md"
    now = datetime.now()
    build_date = now.strftime(f"%B {now.day}, %Y")
    parts: list[str] = [
        "% BAS Build Specification\n",
        "% Generated by tools/build_bas_spec_pdf.py\n",
        f"% {build_date}\n\n",
        f"*Generated {build_date}*\n\n",
        "This bundle is the orchestration workspace for the BAS head-end: product "
        "rules, acceptance criteria, agent skills, memory, and cron/Codex automation. "
        "Generated application code lives in the sibling `bas_app/` directory.\n\n",
        "---\n\n",
    ]

    for path in files:
        fm, body = parse_front_matter(path)
        if fm.get("nav_exclude"):
            continue
        rel = path.relative_to(SPEC_ROOT)
        parts.append(f"# {title_for(path, fm)}\n\n")
        parts.append(f"*Source: `{rel}`*\n\n")
        parts.append(strip_kramdown_ial(body))
        if not body.endswith("\n"):
            parts.append("\n")
        parts.append("\n\n")

    combined_md = "".join(parts)
    combined_path.write_text(combined_md, encoding="utf-8")
    print(f"Wrote {len(files)} sections to {combined_path}")

    output = args.output if args.output.is_absolute() else SPEC_ROOT / args.output
    txt_output = output.with_suffix(".txt")
    output.parent.mkdir(parents=True, exist_ok=True)
    txt_output.write_text(combined_md, encoding="utf-8")
    print(f"Wrote LLM context text to {txt_output}")

    if args.no_pdf:
        print("Skipping PDF (--no-pdf).")
        return 0

    pdf_engine = args.pdf_engine or default_pdf_engine()
    cmd = [
        pandoc_path(),
        str(combined_path),
        "-o",
        str(output),
        "--toc",
        "--number-sections",
        pdf_engine_arg(pdf_engine),
    ]
    if pdf_engine in {"pdflatex", "xelatex"}:
        cmd.extend(
            [
                "-V",
                "documentclass=article",
                "-V",
                "papersize=letter",
                "-V",
                "geometry:margin=1in",
                "-V",
                f"date={build_date}",
            ]
        )
    elif pdf_engine == "typst":
        cmd.extend(["-V", f"date={build_date}"])
    print(f"Running: {' '.join(cmd)}")
    env = os.environ.copy()
    py_bin = str(Path(sys.executable).resolve().parent)
    tool_bin = str(TOOLS_BIN.resolve())
    env["PATH"] = os.pathsep.join([tool_bin, py_bin, env.get("PATH", "")])
    try:
        subprocess.run(cmd, check=True, cwd=SPEC_ROOT, env=env)
    except FileNotFoundError:
        print("pandoc not found. Install pandoc or use tools/bin/pandoc.", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(
            f"Pandoc PDF failed (engine={pdf_engine}). "
            "Place typst in tools/bin, install weasyprint system deps, or use --pdf-engine=pdflatex.",
            file=sys.stderr,
        )
        return exc.returncode

    print(f"PDF written to {output}")
    if not args.keep_md:
        combined_path.unlink(missing_ok=True)
        if BUILD_DIR.exists() and not any(BUILD_DIR.iterdir()):
            BUILD_DIR.rmdir()
    return 0


if __name__ == "__main__":
    sys.exit(main())
