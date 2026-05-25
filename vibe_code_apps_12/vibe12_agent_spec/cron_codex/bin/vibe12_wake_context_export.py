#!/usr/bin/env python3
"""Export operator + commissioning context for vibe12_wake (since last wake)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _extract_notepad_pin(text: str) -> str:
    start_markers = ("## § A", "## A)", "## A )")
    end_markers = ("## § F", "## F)")
    start = -1
    for marker in start_markers:
        idx = text.find(marker)
        if idx >= 0:
            start = idx
            break
    if start < 0:
        body = text.strip()
        return body[:6000] if body else "_PHASE_NOTEPAD empty._"
    end = len(text)
    for marker in end_markers:
        idx = text.find(marker, start)
        if idx > start:
            end = idx
            break
    body = text[start:end]
    if len(body) > 5000:
        body = body[:5000] + "\n…(notepad pinned section truncated)…"
    return body.strip()


def main() -> int:
    if len(sys.argv) < 6:
        print(
            "usage: vibe12_wake_context_export.py "
            "<last_wake_epoch_file> <operator_notes.md> <PHASE_NOTEPAD.md> "
            "<out_context.md> <out.meta.json>",
            file=sys.stderr,
        )
        return 2

    epoch_file = Path(sys.argv[1])
    operator_path = Path(sys.argv[2])
    notepad_path = Path(sys.argv[3])
    out_md = Path(sys.argv[4])
    out_meta = Path(sys.argv[5])

    last_epoch = 0
    if epoch_file.is_file():
        try:
            last_epoch = int(epoch_file.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            last_epoch = 0

    last_wake_iso = (
        datetime.fromtimestamp(last_epoch, tz=timezone.utc).isoformat()
        if last_epoch > 0
        else "(no prior wake epoch — first export)"
    )

    lines: list[str] = [
        "# Wake context export (Vibe12)",
        "",
        f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}",
        f"Cutoff (last wake epoch): {last_wake_iso}",
        "",
        "Codex (**mini and gpt-5.5 critique**): read this entire file every wake.",
        "Execute **BUILD_CHECKPOINTS.md → Next for mini (ordered)** from the last critique.",
        "",
    ]

    if operator_path.is_file():
        notes = operator_path.read_text(encoding="utf-8", errors="replace").strip()
        if not notes:
            notes = "_operator_notes.md is empty._"
        elif len(notes) > 8000:
            notes = notes[:8000] + "\n…(operator notes truncated)…"
        lines.extend(["## Operator notes (human)", "", notes, "", "---", ""])
    else:
        lines.extend(
            [
                "## Operator notes (human)",
                "",
                f"_Not found: `{operator_path}` — create and append notes between wakes._",
                "",
                "---",
                "",
            ]
        )

    if notepad_path.is_file():
        pinned = _extract_notepad_pin(notepad_path.read_text(encoding="utf-8", errors="replace"))
        lines.extend(
            [
                "## Pinned site context (PHASE_NOTEPAD.md)",
                "",
                "_Always read — bind, devices, URLs survive empty operator notes._",
                "",
                pinned,
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Pinned site context (PHASE_NOTEPAD.md)",
                "",
                f"_Not found: `{notepad_path}`_",
                "",
            ]
        )

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")

    meta = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "last_wake_epoch": last_epoch,
        "last_wake_iso": last_wake_iso,
        "operator_notes": str(operator_path),
        "phase_notepad": str(notepad_path),
        "context_md": str(out_md),
    }
    out_meta.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_md} ({len(lines)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
