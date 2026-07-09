"""Per-page analyst notes as timestamped blog posts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def migrate_notes(raw: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Normalize legacy {page: str} notes into {page: [{id, ts, author, text}]}."""
    out: dict[str, list[dict[str, str]]] = {}
    for page, val in (raw or {}).items():
        if isinstance(val, str):
            text = val.strip()
            if text:
                out[page] = [{"id": "legacy", "ts": "", "author": "", "text": text}]
            else:
                out[page] = []
        elif isinstance(val, list):
            posts = []
            for item in val:
                if isinstance(item, dict) and item.get("text"):
                    posts.append({
                        "id": str(item.get("id") or uuid.uuid4().hex[:12]),
                        "ts": str(item.get("ts") or ""),
                        "author": str(item.get("author") or ""),
                        "text": str(item["text"]),
                    })
            out[page] = posts
        else:
            out[page] = []
    return out


def posts_for_page(notes: dict[str, Any], page_id: str) -> list[dict[str, str]]:
    migrated = migrate_notes(notes)
    return list(migrated.get(page_id, []))


def add_post(
    notes: dict[str, Any],
    page_id: str,
    text: str,
    *,
    author: str = "",
) -> dict[str, str]:
    migrated = migrate_notes(notes)
    post = {
        "id": uuid.uuid4().hex[:12],
        "ts": _now_iso(),
        "author": author.strip(),
        "text": text.strip(),
    }
    migrated.setdefault(page_id, []).insert(0, post)
    notes.clear()
    notes.update(migrated)
    return post


def delete_post(notes: dict[str, Any], page_id: str, post_id: str) -> bool:
    migrated = migrate_notes(notes)
    posts = migrated.get(page_id, [])
    new_posts = [p for p in posts if p.get("id") != post_id]
    if len(new_posts) == len(posts):
        return False
    migrated[page_id] = new_posts
    notes.clear()
    notes.update(migrated)
    return True
