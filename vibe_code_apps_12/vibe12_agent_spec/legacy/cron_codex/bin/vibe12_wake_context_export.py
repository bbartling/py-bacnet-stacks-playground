#!/usr/bin/env python3
"""Export minimal wake slice — wake_task + short operator notes (not full AGENTS/notepad dump)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


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

    spec_dir = out_md.resolve().parent.parent.parent
    wake_task = spec_dir / "cron_codex" / "state" / "wake_task.md"
    lab_facts = spec_dir / "memory" / "job" / "lab_facts.md"

    last_epoch = 0
    if epoch_file.is_file():
        try:
            last_epoch = int(epoch_file.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            last_epoch = 0

    last_wake_iso = (
        datetime.fromtimestamp(last_epoch, tz=timezone.utc).isoformat()
        if last_epoch > 0
        else "(no prior wake epoch)"
    )

    lines: list[str] = [
        "# Wake slice (minimal)",
        "",
        f"Generated (UTC): {datetime.now(timezone.utc).isoformat()} · since wake: {last_wake_iso}",
        "",
        "Read **only** (do not paste file contents into replies):",
        "",
        f"1. `{wake_task.relative_to(spec_dir)}` — **current mission** (critique-written)",
        f"2. `{lab_facts.relative_to(spec_dir)}` — IPs, device 5007, URLs (no secrets)",
        "3. `GUARDRAILS.md` — if unsure about writes",
        "",
        "Skills: open `skills/<name>/SKILL.md` only when wake_task names a skill.",
        "Secrets: `WEB_PASSWORD` / SSH — never read `samconfig.toml`.",
        "",
    ]

    if wake_task.is_file():
        task_body = wake_task.read_text(encoding="utf-8", errors="replace").strip()
        if len(task_body) > 2500:
            task_body = task_body[:2500] + "\n…(wake_task truncated)…"
        lines.extend(["## wake_task.md", "", task_body, "", "---", ""])
    else:
        lines.extend(
            [
                "## wake_task.md",
                "",
                "_Missing — run `/critique` to set the next mission, or copy from "
                "`templates/cron_codex/state/wake_task.example.md`._",
                "",
                "---",
                "",
            ]
        )

    if operator_path.is_file():
        notes = operator_path.read_text(encoding="utf-8", errors="replace").strip()
        if not notes:
            notes = "_empty_"
        elif len(notes) > 1500:
            notes = notes[:1500] + "\n…(truncated)…"
        lines.extend(["## Operator notes", "", notes, ""])
    else:
        lines.append("## Operator notes\n\n_none_\n")

    if not lab_facts.is_file():
        lines.extend(
            [
                "",
                f"_Tip: copy `templates/memory/job/lab_facts.example.md` → `{lab_facts.relative_to(spec_dir)}`._",
            ]
        )

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")

    meta = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "last_wake_epoch": last_epoch,
        "last_wake_iso": last_wake_iso,
        "wake_task": str(wake_task),
        "lab_facts": str(lab_facts),
        "operator_notes": str(operator_path),
        "phase_notepad": str(notepad_path),
        "context_md": str(out_md),
        "mode": "minimal",
    }
    out_meta.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
