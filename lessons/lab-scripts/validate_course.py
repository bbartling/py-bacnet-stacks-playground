#!/usr/bin/env python3
"""Offline course QA: documents, public fixture hashes, and tiny Rust examples.

No sockets, hardware, sudo, dependency installation, or student solutions.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = {7, 14, 19, 28, 35, 42, 49, 56, 63, 70, 77, 84, 91, 98, 105, 112}


def anchors(text):
    result = set(re.findall(r'<a\s+id="([^"]+)"', text))
    seen = {}
    for title in re.findall(r'^#{1,6}\s+(.+)$', text, re.M):
        title = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', title)
        slug = re.sub(r'[^\w\- ]', '', title.lower()).replace(' ', '-')
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug if not count else f'{slug}-{count}')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rust-examples', action='store_true', help='compile and run complete std-only Rust snippets offline')
    args = parser.parse_args()
    errors = []
    days = [ROOT / f'day{n:02}.md' for n in range(1, 113)]
    actual = set(ROOT.glob('day[0-9]*.md'))
    if actual != set(days):
        errors.append(f'day-file set mismatch: {sorted(str(p.name) for p in actual ^ set(days))}')
    snippets = []
    for n, path in enumerate(days, 1):
        if not path.exists():
            errors.append(f'missing {path.name}')
            continue
        text = path.read_text()
        if not text.startswith(f'# Day {n:02} — '):
            errors.append(f'{path.name}: title/day mismatch')
        required = ('Project brief', 'Acceptance criteria', 'Deliverables', 'Self-review') if n in REVIEWS else ('Goal', 'Before you start', 'Concept', 'Tiny example', 'Coding challenge', 'Experiment', 'Acceptance checks', 'Optional Python companion', 'Stretch and reflection')
        for heading in required:
            if f'## {heading}\n' not in text:
                errors.append(f'{path.name}: missing {heading}')
        if n in REVIEWS and '```' in text:
            errors.append(f'{path.name}: review contains a code fence; inspect for spoilers')
        if text.count('```') % 2:
            errors.append(f'{path.name}: unmatched code fence')
        if len(text.split()) < 200:
            errors.append(f'{path.name}: unexpectedly short lesson')
        for block in re.findall(r'```rust\n(.*?)\n```', text, re.S):
            snippets.append((path.name, block))
    docs = days + [ROOT / name for name in ('INDEX.md', 'LAB_GUIDE.md', 'WIRE_FORMATS.md', 'TOPOLOGIES.md', 'SOURCES.md', 'VALIDATION.md', 'capstone/README.md', 'lab-scripts/wireshark_filters.md')]
    docs += sorted((ROOT / 'fixtures').rglob('*.md'))
    link_count = 0
    for path in docs:
        if not path.exists():
            errors.append(f'missing support doc: {path}')
            continue
        text = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
        for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', text):
            if re.match(r'^[a-z]+://|^mailto:', target):
                continue
            file_part, _, fragment = unquote(target).partition('#')
            resolved = (path.parent / file_part).resolve() if file_part else path
            link_count += 1
            if not resolved.exists():
                errors.append(f'{path.relative_to(ROOT)}: missing target {target}')
            elif fragment and resolved.is_file() and resolved.suffix == '.md' and fragment not in anchors(resolved.read_text()):
                errors.append(f'{path.relative_to(ROOT)}: missing anchor {target}')
    index = (ROOT / 'INDEX.md').read_text()
    scheduled = [int(n) for n in re.findall(r'^\| (?:\*\*)?\[(\d+)\]\(day\d+\.md\)', index, re.M)]
    if scheduled != list(range(1, 113)):
        errors.append('INDEX: schedule does not contain Days 1–112 exactly once in order')
    manifest = json.loads((ROOT / 'fixtures/manifest.json').read_text())
    for rel, expected in manifest.items():
        path = ROOT / 'fixtures' / rel
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f'fixture hash mismatch: {rel}')
    if args.rust_examples:
        if not shutil.which('rustc'):
            errors.append('rustc missing; cannot check Rust examples')
        else:
            with tempfile.TemporaryDirectory(prefix='course-rust-qa-') as directory:
                folder = Path(directory)
                for i, (name, block) in enumerate(snippets):
                    source = folder / f'example_{i}.rs'
                    binary = folder / f'example_{i}'
                    source.write_text(block + '\n')
                    try:
                        built = subprocess.run(['rustc', '--edition', '2024', str(source), '-o', str(binary)], capture_output=True, text=True, timeout=30)
                        if built.returncode:
                            errors.append(f'{name}: Rust compile failed: {built.stderr.strip()}')
                            continue
                        # The bind demonstration is compile-checked only: this validator opens no sockets.
                        if 'UdpSocket::bind' in block or 'to_socket_addrs' in block:
                            continue
                        ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                        if ran.returncode:
                            errors.append(f'{name}: Rust example failed: {ran.stderr.strip()}')
                    except subprocess.TimeoutExpired:
                        errors.append(f'{name}: example exceeded QA timeout')
    if errors:
        print('\n'.join('FAIL: ' + error for error in errors))
        raise SystemExit(1)
    print(f'PASS: 112 lessons, {len(REVIEWS)} review briefs, {link_count} local links/anchors, {len(manifest)} fixture hashes.')
    print(f'Complete std-only Rust examples: {len(snippets)}' + (' compiled; non-network examples executed.' if args.rust_examples else ' (not compiled; add --rust-examples).'))
    print('Live network, independent stack, Pi, serial and appliance-image labs are not run by this checker.')


if __name__ == '__main__':
    main()
