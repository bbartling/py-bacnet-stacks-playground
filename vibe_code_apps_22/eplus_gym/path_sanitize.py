"""Redact machine-local paths from JSON artifacts. Preserve numeric metrics."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_WIN_USER = re.compile(r"[A-Za-z]:\\Users\\[^\\]+\\", re.I)
_POSIX_USER = re.compile(r"/Users/[^/]+/")
_SITE_HINT = re.compile(r"sp_creekside", re.I)


def redact_text(text: str) -> str:
    out = _WIN_USER.sub("<USER_HOME>/", text)
    out = _POSIX_USER.sub("<USER_HOME>/", out)
    if _SITE_HINT.search(out):
        out = re.sub(r"<USER_HOME>/[^\"]*sp_creekside", "<SITE_ROOT>", out, flags=re.I)
    return out


def redact_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, list):
        return [redact_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    return obj


def redact_json_file(path: Path) -> bool:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    cleaned = redact_obj(data)
    text = json.dumps(cleaned, indent=2) + "\n"
    if text != json.dumps(data, indent=2) + "\n" or _WIN_USER.search(raw) or _POSIX_USER.search(raw):
        path.write_text(text, encoding="utf-8")
        return True
    return False
