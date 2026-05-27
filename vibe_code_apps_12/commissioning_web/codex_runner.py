"""Run a single codex exec prompt (JSON quiet mode) for the commissioning chat."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = APP_ROOT / "vibe12_agent_spec"
ENV_FILE = SPEC_DIR / "cron_codex" / ".env"

_SECRET_LINE = re.compile(
    r"(WebPassword|AuthSecret|AWS_SECRET|AWS_ACCESS_KEY|private\.key)\s*[=:]\s*\S+",
    re.I,
)


def _load_dotenv() -> None:
    if not ENV_FILE.is_file():
        return
    for raw in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _codex_bin() -> str:
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("codex CLI not found on PATH")
    return codex


def _mini_model() -> str:
    return os.environ.get("MINI_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini"


def _bwrap_ok() -> bool:
    if not shutil.which("bwrap"):
        return False
    try:
        subprocess.run(
            ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--unshare-net", "--", "true"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def _sandbox_args() -> list[str]:
    """Commissioning dashboard defaults to full access (bwrap often breaks on bensserver)."""
    mode = os.environ.get("VIBE12_COMMISSION_SANDBOX", "").strip().lower()
    if mode in ("workspace-write", "write", "none", "off"):
        if mode in ("none", "off"):
            return []
        return ["-s", "workspace-write"]

    if os.environ.get("VIBE12_COMMISSION_NO_BYPASS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        if _bwrap_ok():
            return ["-s", "workspace-write"]
        return ["--dangerously-bypass-approvals-and-sandbox"]

    # Default: bypass sandbox so ansible/ssh/ping work from codex on bensserver
    if os.environ.get("VIBE12_CODEX_BYPASS_SANDBOX", "").strip().lower() in ("1", "true", "yes"):
        return ["--dangerously-bypass-approvals-and-sandbox"]
    if os.environ.get("CODEX_DANGEROUSLY_BYPASS", "").strip().lower() in ("1", "true", "yes"):
        return ["--dangerously-bypass-approvals-and-sandbox"]
    if not _bwrap_ok():
        return ["--dangerously-bypass-approvals-and-sandbox"]
    return ["--dangerously-bypass-approvals-and-sandbox"]


def _skills_index() -> str:
    lines = [
        "Before acting, read each skill file in full (on disk under vibe12_agent_spec/skills/):",
    ]
    skills_dir = SPEC_DIR / "skills"
    if skills_dir.is_dir():
        for path in sorted(skills_dir.glob("*/SKILL.md")):
            rel = path.relative_to(APP_ROOT)
            lines.append(f"  - {rel}")
    lines.extend(
        [
            "Also read: vibe12_agent_spec/AGENTS.md, vibe12_agent_spec/GUARDRAILS.md",
            "Context: vibe12_agent_spec/cron_codex/state/wake_task.md, memory/job/lab_facts.md",
            f"Work in repo: {APP_ROOT}",
            "",
            "--- User mission ---",
            "",
        ]
    )
    return "\n".join(lines)


def wrap_prompt_for_codex(user_prompt: str) -> str:
    return _skills_index() + user_prompt.strip()


def _build_cmd() -> list[str]:
    codex = _codex_bin()
    cmd = [codex, "exec", "--json", "-C", str(APP_ROOT), "-m", _mini_model()]
    cmd.extend(_sandbox_args())
    cmd.append("--color")
    cmd.append("never")
    extra = os.environ.get("VIBE12_CODEX_EXTRA", "").strip()
    if extra:
        cmd.extend(shlex.split(extra))
    return cmd


def _parse_json_stdout(stdout: str) -> tuple[str, str]:
    replies: list[str] = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "item.completed":
            continue
        item = event.get("item") or {}
        if item.get("type") == "agent_message":
            text = (item.get("text") or "").strip()
            if text:
                replies.append(text)
    final = replies[-1] if replies else ""
    return final, stdout


def run_codex_prompt(user_prompt: str, log_path: Path | None = None) -> dict[str, object]:
    """Run one codex exec; user_prompt is wrapped with skills index for the agent."""
    _load_dotenv()
    if not user_prompt.strip():
        return {"exit_code": 2, "final_reply": "", "error": "empty prompt"}

    full_prompt = wrap_prompt_for_codex(user_prompt)
    cmd = _build_cmd()
    cmd.append(full_prompt)

    proc = subprocess.run(
        cmd,
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        timeout=int(os.environ.get("VIBE12_CODEX_TIMEOUT_SEC", "3600")),
    )

    stderr = proc.stderr or ""
    if proc.stdout:
        final, _raw = _parse_json_stdout(proc.stdout)
    else:
        final, _raw = "", ""

    if not final and stderr:
        final = stderr[-4000:]

    log_text = (
        f"# sandbox: {' '.join(_sandbox_args())}\n"
        f"# exit: {proc.returncode}\n\n"
        f"{_redact(stderr)}\n\n--- stdout (tail) ---\n{(proc.stdout or '')[-8000:]}"
    )
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(log_text, encoding="utf-8")

    return {
        "exit_code": proc.returncode,
        "final_reply": final,
        "error": "" if proc.returncode == 0 else (stderr[-500:] or "codex failed"),
        "sandbox": " ".join(_sandbox_args()),
    }


def _redact(text: str) -> str:
    return _SECRET_LINE.sub(lambda m: f"{m.group(1)}=***", text)
