#!/usr/bin/env python3
"""Export rough-in chat messages posted since the last bas_wake run."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _parse_ts(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _last_wake_utc(jobs_state_path: Path) -> datetime | None:
    if not jobs_state_path.is_file():
        return None
    try:
        state = json.loads(jobs_state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    meta = state.get("bas-wake-hourly") or {}
    return _parse_ts(str(meta.get("last_run_at", "")))


def _extract_notepad_pin(text: str) -> str:
    """Sections A–E tables (durable site facts), skip chronological log."""
    start_markers = ("## A)", "## A )")
    end_marker = "## F)"
    start = -1
    for marker in start_markers:
        idx = text.find(marker)
        if idx >= 0:
            start = idx
            break
    if start < 0:
        return text.strip()[:6000] if text.strip() else "_PHASE_NOTEPAD empty._"
    end = text.find(end_marker, start)
    body = text[start:end] if end > start else text[start:]
    return body.strip()


def _pinned_notepad_block(notepad_path: Path) -> list[str]:
    if not notepad_path.is_file():
        return [
            "## Pinned site context (from PHASE_NOTEPAD.md)",
            "",
            f"_Not found: `{notepad_path}`_",
            "",
        ]
    raw = notepad_path.read_text(encoding="utf-8")
    pinned = _extract_notepad_pin(raw)
    if len(pinned) > 5000:
        pinned = pinned[:5000] + "\n…(notepad pinned section truncated)…"
    return [
        "## Pinned site context (from PHASE_NOTEPAD.md)",
        "",
        "_Always read — survives across wakes even when chat slice is empty._",
        "",
        pinned,
        "",
        "---",
        "",
    ]


def _load_chat(chat_path: Path) -> list[dict]:
    if not chat_path.is_file():
        return []
    try:
        payload = json.loads(chat_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    messages = payload.get("messages", [])
    if not isinstance(messages, list):
        return []
    return [m for m in messages if isinstance(m, dict)]


def build_slice(
    *,
    chat_path: Path,
    jobs_state_path: Path,
    out_path: Path,
    meta_path: Path | None = None,
    notepad_path: Path | None = None,
) -> dict:
    since = _last_wake_utc(jobs_state_path)
    all_messages = _load_chat(chat_path)
    if since is None:
        selected = all_messages
        since_label = "(no prior wake in jobs-state — full transcript)"
    else:
        selected = []
        for message in all_messages:
            created = _parse_ts(str(message.get("created_at", "")))
            if created is None:
                continue
            if created > since:
                selected.append(message)

    user_count = sum(1 for m in selected if m.get("role") == "user")
    assistant_count = sum(1 for m in selected if m.get("role") == "assistant")

    notepad = notepad_path or Path()
    lines = [
        "# Rough-in commissioning context (wake export)",
        "",
        f"Generated (UTC): {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
        f"Cutoff (last bas_wake `last_run_at`): {since.isoformat().replace('+00:00', 'Z') if since else since_label}",
        f"Chat source: `{chat_path}`",
        f"Messages since cutoff: {len(selected)} (user: {user_count}, assistant: {assistant_count})",
        "",
        "Codex (**mini and gpt-5.5 critique**): read this entire file every wake.",
        "Do not rely on `rough_in_chat_summary.md` (latest turn only).",
        "",
    ]
    lines.extend(_pinned_notepad_block(notepad))
    lines.extend(
        [
            "## Chat since last bas_wake",
            "",
        ]
    )

    if not selected:
        lines.append("_No new rough-in chat messages since the last wake._")
    else:
        for index, message in enumerate(selected, start=1):
            role = str(message.get("role", "?"))
            created = str(message.get("created_at", ""))
            content = str(message.get("content", "")).strip()
            if len(content) > 4000:
                content = content[:4000] + "\n…(truncated for wake prompt)…"
            lines.extend(
                [
                    f"## {index}. {role} @ {created}",
                    "",
                    content,
                    "",
                ]
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    meta = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "since_utc": since.isoformat().replace("+00:00", "Z") if since else None,
        "since_label": since_label if since is None else None,
        "chat_path": str(chat_path),
        "jobs_state_path": str(jobs_state_path),
        "notepad_path": str(notepad_path) if notepad_path else None,
        "notepad_pinned": bool(notepad_path and notepad_path.is_file()),
        "out_path": str(out_path),
        "message_count": len(selected),
        "user_count": user_count,
        "assistant_count": assistant_count,
    }
    if meta_path is not None:
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return meta


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(
            "usage: bas_rough_in_chat_since_wake.py <chat.json> <jobs-state.json> <out.md> [meta.json] [PHASE_NOTEPAD.md]",
            file=sys.stderr,
        )
        return 2
    chat_path = Path(argv[1]).expanduser()
    jobs_state_path = Path(argv[2]).expanduser()
    out_path = Path(argv[3]).expanduser()
    meta_path: Path | None = None
    notepad_path: Path | None = None
    if len(argv) > 4:
        arg4 = Path(argv[4]).expanduser()
        if arg4.suffix == ".json":
            meta_path = arg4
            if len(argv) > 5:
                notepad_path = Path(argv[5]).expanduser()
        else:
            notepad_path = arg4
            if len(argv) > 5:
                meta_path = Path(argv[5]).expanduser()
    meta = build_slice(
        chat_path=chat_path,
        jobs_state_path=jobs_state_path,
        out_path=out_path,
        meta_path=meta_path,
        notepad_path=notepad_path,
    )
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
