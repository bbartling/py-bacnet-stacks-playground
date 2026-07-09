"""ML lab backend — local-dev helpers for the custom/ML rule page.

Provides three capabilities the analyst/ML workflow asked for:
  1. Upload a `.py` rule plugin and read it back (rendered read-only in the browser).
  2. `pip install` packages an ML author wants into the running interpreter's venv.
  3. Persist a computed fault series back to the Feather store as a proof of concept
     (ML in pandas -> boolean fault mask -> Feather sidecar under .cache/feather/faults).

SECURITY NOTE: This is a **local, single-user analyst** surface. Uploading Python and
running pip execute code on the host by design. Keep this behind `DASHBOARD_MODE=full`
on a trusted machine; never expose it publicly. Uploaded files land in `rules/plugins/`
and are imported by the rule registry exactly like shipped plugins.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent
PLUGIN_DIR = ROOT / "rules" / "plugins"
FAULT_STORE_DIR = ROOT / ".cache" / "feather" / "faults"

MAX_UPLOAD_BYTES = 250_000
MAX_PIP_PACKAGES = 12
PIP_TIMEOUT_SEC = 600

# Example plugins shipped with the repo — protected from overwrite/delete via the UI.
PROTECTED_PLUGINS = {"custom_sat_hunting.py", "ml_oat_residual.py", "ml_sat_linear_residual.py"}

# One package token: name, optional extras [..], optional version spec. No shell metachars.
_PKG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*(\[[A-Za-z0-9._,\-]+\])?([=<>!~]=?[A-Za-z0-9._\-]+)*$")


# ---------------------------------------------------------------------------
# Plugin upload / listing / read
# ---------------------------------------------------------------------------


def safe_module_name(filename: str) -> str:
    stem = Path(filename or "").name
    if stem.endswith(".py"):
        stem = stem[:-3]
    stem = re.sub(r"[^0-9A-Za-z_]", "_", stem).strip("_").lower()
    if not stem:
        stem = "uploaded_rule"
    if stem[0].isdigit():
        stem = f"ml_{stem}"
    return f"{stem}.py"


def save_upload(filename: str, content: bytes) -> dict[str, Any]:
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File too large ({len(content)} bytes > {MAX_UPLOAD_BYTES}).")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"File is not valid UTF-8 text: {exc}") from exc
    # Reject binary / non-python quickly: require it to at least parse as Python.
    try:
        compile(text, filename or "<upload>", "exec")
    except SyntaxError as exc:
        raise ValueError(f"Not valid Python (SyntaxError line {exc.lineno}): {exc.msg}") from exc

    name = safe_module_name(filename)
    PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    dest = PLUGIN_DIR / name
    dest.write_text(text, encoding="utf-8")
    return {"name": name, "bytes": len(content), "path": str(dest)}


def list_plugins() -> list[dict[str, Any]]:
    if not PLUGIN_DIR.is_dir():
        return []
    out = []
    for p in sorted(PLUGIN_DIR.glob("*.py")):
        if p.name.startswith("_"):
            continue
        st = p.stat()
        out.append({
            "name": p.name,
            "bytes": st.st_size,
            "mtime": st.st_mtime,
            "protected": p.name in PROTECTED_PLUGINS,
        })
    return out


def read_plugin(name: str) -> str:
    safe = Path(name).name
    path = PLUGIN_DIR / safe
    if not path.is_file() or path.parent.resolve() != PLUGIN_DIR.resolve():
        raise FileNotFoundError(f"No plugin named {safe}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# pip install
# ---------------------------------------------------------------------------


def _validate_packages(raw: str | list[str]) -> list[str]:
    tokens = raw.split() if isinstance(raw, str) else list(raw)
    tokens = [t.strip() for t in tokens if t and t.strip()]
    if not tokens:
        raise ValueError("No packages specified.")
    if len(tokens) > MAX_PIP_PACKAGES:
        raise ValueError(f"Too many packages (max {MAX_PIP_PACKAGES}).")
    for t in tokens:
        if not _PKG_RE.match(t):
            raise ValueError(f"Rejected package spec (unsafe characters): {t!r}")
    return tokens


def pip_install(raw: str | list[str]) -> dict[str, Any]:
    packages = _validate_packages(raw)
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *packages]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=PIP_TIMEOUT_SEC, check=False,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "packages": packages,
            "command": " ".join(cmd[1:]),
            "output": output[-12000:],
            "elapsed_s": round(time.time() - t0, 1),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -1, "packages": packages,
                "command": " ".join(cmd[1:]), "output": f"pip timed out after {PIP_TIMEOUT_SEC}s",
                "elapsed_s": round(time.time() - t0, 1)}


# ---------------------------------------------------------------------------
# Persist a fault series to the Feather store (proof of concept)
# ---------------------------------------------------------------------------


def _fault_store_paths(equipment_id: str, rule_id: str) -> tuple[Path, Path]:
    safe = re.sub(r"[^0-9A-Za-z_.\-]", "_", f"{equipment_id}__{rule_id}")
    base = FAULT_STORE_DIR / safe
    return base.with_suffix(".feather"), base.with_suffix(".meta.json")


def persist_fault(
    equipment_id: str,
    rule_id: str,
    fault_series: pd.Series,
    *,
    timestamps: pd.Series | None = None,
    poll_seconds: float = 300.0,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a boolean fault series to a Feather sidecar and read it back to verify."""
    fault = fault_series.fillna(False).astype(bool).reset_index(drop=True)
    df = pd.DataFrame({"fault_confirmed": fault.astype("int8")})
    if timestamps is not None:
        ts = pd.to_datetime(pd.Series(timestamps).reset_index(drop=True), errors="coerce", utc=True)
        df.insert(0, "timestamp", ts)

    FAULT_STORE_DIR.mkdir(parents=True, exist_ok=True)
    feather_path, meta_path = _fault_store_paths(equipment_id, rule_id)
    df.to_feather(feather_path)

    fault_rows = int(fault.sum())
    total_rows = int(len(fault))
    fault_hours = round(fault_rows * poll_seconds / 3600.0, 2)
    summary = {
        "equipment_id": equipment_id,
        "rule_id": rule_id,
        "rows": total_rows,
        "fault_rows": fault_rows,
        "fault_hours": fault_hours,
        "poll_seconds": poll_seconds,
        "feather_path": str(feather_path),
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        **(meta or {}),
    }
    meta_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Read-back verification — prove the store round-trips.
    check = pd.read_feather(feather_path)
    summary["verify_rows"] = int(len(check))
    summary["verify_fault_rows"] = int(check["fault_confirmed"].sum())
    summary["verified"] = (
        summary["verify_rows"] == total_rows and summary["verify_fault_rows"] == fault_rows
    )
    return summary


def list_fault_stores() -> list[dict[str, Any]]:
    if not FAULT_STORE_DIR.is_dir():
        return []
    out = []
    for meta_path in sorted(FAULT_STORE_DIR.glob("*.meta.json")):
        try:
            out.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out
