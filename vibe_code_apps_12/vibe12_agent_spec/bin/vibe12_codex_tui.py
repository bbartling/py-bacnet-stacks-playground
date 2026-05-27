#!/usr/bin/env python3
"""
Dirt-simple REPL around `codex exec` for vibe_code_apps_12.

Model routing (default):
  - gpt-5.4-mini  → normal work (/mini, default prompts)
  - gpt-5.5       → critique only (/critique)

  cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
  vibe12_agent_spec/bin/vibe12_codex_tui.py

Config: vibe12_agent_spec/cron_codex/.env (copy from cron_codex/env.example)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parent.parent
APP_ROOT = SPEC_DIR.parent
ENV_FILE = SPEC_DIR / "cron_codex" / ".env"
CRON_BIN = SPEC_DIR / "cron_codex" / "bin"
WAKE_TASK = SPEC_DIR / "cron_codex" / "state" / "wake_task.md"
LAB_FACTS = SPEC_DIR / "memory" / "job" / "lab_facts.md"
CONTEXT_SLICE = SPEC_DIR / "cron_codex" / "state" / "context_since_last_wake.md"
SESSION_FILE = SPEC_DIR / "cron_codex" / "state" / "codex_tui_session.json"
WAKE_SCRIPT = CRON_BIN / "vibe12_wake.sh"

MINI_PREAMBLE = """Vibe12 mini — one mission only.

Read on disk (never paste back): vibe12_agent_spec/cron_codex/state/wake_task.md (primary), memory/job/lab_facts.md (IPs/device/URLs), GUARDRAILS.md if blocked.
Open vibe12_agent_spec/skills/<name>/SKILL.md only if wake_task names a skill.
Do NOT read AGENTS.md or BUILD_CHECKPOINTS.md unless wake_task says to.
Secrets: WEB_PASSWORD env, Pi SSH — never samconfig.toml.

User request:
"""

CRITIQUE_PROMPT_TEMPLATE = """You are the CRITIQUE pass ({critique_model}) on vibe_code_apps_12. Plan only — no feature code.

Read: BUILD_CHECKPOINTS.md, git diff, memory/{today}.md, cron_codex/state/operator_notes.md, memory/job/lab_facts.md.

Write / update:
1) **cron_codex/state/wake_task.md** — ONE current mission for the next mini(s): what to do now, which skill, done-when checklist, and **Escalation** if {mini_model} is stuck (concrete recovery steps or "critique re-run needed").
2) **BUILD_CHECKPOINTS.md** — Last critique, Current sprint, **Next for mini (ordered)** (max 3 items; backlog lives in wake_task).
3) **memory/job/lab_facts.md** — keep IPs, device 5007, URLs current (no passwords).
4) Append one paragraph to memory/{today}.md.

If minis failed or ignored wake_task, fix wake_task and escalation — do not add more queue items until clear.

Optional operator notes:
{user_notes}
"""


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
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


def _model(name: str, *fallback_keys: str, default: str) -> str:
    for key in (name, *fallback_keys):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return default


def _mini_model() -> str:
    return _model(
        "VIBE12_MINI_MODEL",
        "MINI_MODEL",
        default="gpt-5.4-mini",
    )


def _critique_model() -> str:
    return _model(
        "VIBE12_CRITIQUE_MODEL",
        "CRITIQUE_MODEL",
        default="gpt-5.5",
    )


def _forced_model() -> str | None:
    """Single model for all turns — disables routing."""
    return os.environ.get("VIBE12_CODEX_MODEL", "").strip() or None


def _codex_bin() -> str:
    path = os.environ.get("CODEX_BIN") or shutil.which("codex")
    if not path:
        sys.stderr.write("codex not found on PATH. Install Codex CLI or set CODEX_BIN.\n")
        sys.exit(1)
    return path


_BWRAP_OK: bool | None = None


def _bwrap_loopback_ok() -> bool:
    global _BWRAP_OK
    if _BWRAP_OK is not None:
        return _BWRAP_OK
    bwrap = shutil.which("bwrap")
    if not bwrap:
        _BWRAP_OK = False
        return _BWRAP_OK
    try:
        proc = subprocess.run(
            [bwrap, "--ro-bind", "/", "/", "--dev", "/dev", "--unshare-net", "--", "true"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        _BWRAP_OK = False
        return _BWRAP_OK
    _BWRAP_OK = proc.returncode == 0
    return _BWRAP_OK


def _sandbox_args() -> tuple[list[str], str]:
    bypass_env = os.environ.get("VIBE12_CODEX_BYPASS_SANDBOX", "").strip().lower()
    if bypass_env in ("1", "yes", "true"):
        return ["--dangerously-bypass-approvals-and-sandbox"], "bypass (VIBE12_CODEX_BYPASS_SANDBOX)"

    if "VIBE12_CODEX_SANDBOX" in os.environ:
        mode = os.environ["VIBE12_CODEX_SANDBOX"].strip()
        if not mode or mode == "none":
            return [], "none"
        return ["-s", mode], mode

    if not _bwrap_loopback_ok():
        return ["--dangerously-bypass-approvals-and-sandbox"], "bypass (bwrap broken on this host)"

    return ["-s", "workspace-write"], "workspace-write"


def _base_args(codex: str, *, mode: str) -> list[str]:
    args = [codex, "exec", "-C", str(APP_ROOT)]
    forced = _forced_model()
    if forced:
        args.extend(["-m", forced])
    elif mode == "critique":
        args.extend(["-m", _critique_model()])
    else:
        args.extend(["-m", _mini_model()])
    args.extend(_sandbox_args()[0])
    args.extend(["--color", "never"])
    extra = os.environ.get("VIBE12_CODEX_EXTRA", "").strip()
    if extra:
        args.extend(shlex.split(extra))
    return args


_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_SECRET_LINE = re.compile(
    r"(WebPassword|AuthSecret|AWS_SECRET|AWS_ACCESS_KEY|private\.key)\s*[=:]\s*\S+",
    re.I,
)


def _redact_secrets(line: str) -> str:
    return _SECRET_LINE.sub(lambda m: f"{m.group(1)}=***", line)


def _max_resume_turns() -> int:
    raw = os.environ.get("VIBE12_MINI_MAX_RESUME_TURNS", "6").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 6


def _load_session() -> dict:
    if not SESSION_FILE.is_file():
        return {"mini_turns": 0}
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"mini_turns": 0}


def _save_session(data: dict) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _reset_session() -> None:
    _save_session({"mini_turns": 0})


def _quiet_default(cli_verbose: bool, cli_quiet: bool) -> bool:
    if cli_verbose:
        return False
    if cli_quiet:
        return True
    val = os.environ.get("VIBE12_TUI_QUIET", "true").strip().lower()
    return val not in ("0", "false", "no", "off")


def _stream_codex_output(pipe) -> None:
    """Verbose mode: forward full codex stdout (still redact secrets)."""
    try:
        for raw in iter(pipe.readline, ""):
            print(_redact_secrets(raw.rstrip("\n")), flush=True)
    finally:
        pipe.close()


def _prompt_user_preview(prompt: str, *, mode: str) -> str:
    """One-line label for the human — never the full wrapped prompt."""
    if mode == "critique":
        marker = "Optional operator notes:\n"
        if marker in prompt:
            notes = prompt.split(marker, 1)[1].strip()
            if notes and notes != "(none)":
                return "critique · " + notes.split("\n")[0][:96]
        return "critique · refresh BUILD_CHECKPOINTS queue"
    marker = "User request:\n"
    body = prompt.split(marker, 1)[-1].strip() if marker in prompt else prompt.strip()
    return body.split("\n")[0][:96] or "(empty)"


def _spinner_until(stop: threading.Event) -> None:
    i = 0
    while not stop.wait(0.1):
        frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
        sys.stdout.write(f"\r  {frame} codex working…  ")
        sys.stdout.flush()
        i += 1
    sys.stdout.write("\r" + " " * 28 + "\r")
    sys.stdout.flush()


def _critique_prompt(user_notes: str) -> str:
    today = date.today().isoformat()
    notes = user_notes.strip() or "(none)"
    return CRITIQUE_PROMPT_TEMPLATE.format(
        critique_model=_critique_model(),
        mini_model=_mini_model(),
        today=today,
        user_notes=notes,
    )


def _export_wake_context() -> None:
    exporter = CRON_BIN / "vibe12_wake_context_export.py"
    epoch = SPEC_DIR / "cron_codex" / "logs" / "last_wake_epoch"
    operator = SPEC_DIR / "cron_codex" / "state" / "operator_notes.md"
    notepad = SPEC_DIR / "memory" / "commissioning" / "PHASE_NOTEPAD.md"
    meta = SPEC_DIR / "cron_codex" / "state" / "context_since_last_wake.meta.json"
    if exporter.is_file():
        subprocess.run(
            [
                sys.executable,
                str(exporter),
                str(epoch),
                str(operator),
                str(notepad),
                str(CONTEXT_SLICE),
                str(meta),
            ],
            cwd=str(APP_ROOT),
            check=False,
            capture_output=True,
            text=True,
        )


def _run_orchestrated_wake(mini_count: int | None) -> int:
    if not WAKE_SCRIPT.is_file():
        print(f"missing {WAKE_SCRIPT}", file=sys.stderr)
        return 1
    env = os.environ.copy()
    if mini_count is not None:
        env["MINI_INVOCATIONS_PER_WAKE"] = str(mini_count)
    print(f"\n→ orchestrated wake (minis={mini_count or env.get('MINI_INVOCATIONS_PER_WAKE', '3')}) …\n", flush=True)
    return subprocess.run([str(WAKE_SCRIPT)], cwd=str(APP_ROOT), env=env).returncode


def _wrap_mini_prompt(text: str, *, fresh: bool) -> str:
    if not fresh:
        return text
    # Pointers only — Codex reads files; do not inline AGENTS/bootstrap (saves tokens + TUI noise).
    return MINI_PREAMBLE + text.strip()


def _parse_user_line(line: str) -> tuple[str, str, str]:
    """
    Returns (mode, prompt_text, display_label).
    mode: mini | critique
    """
    stripped = line.strip()
    low = stripped.lower()

    if low in ("/critique", "/c"):
        return "critique", "", "critique (template)"
    if low.startswith("/critique ") or low.startswith("/c "):
        rest = stripped.split(maxsplit=1)[1] if " " in stripped else ""
        return "critique", rest, "critique"

    if low in ("/mini", "/m"):
        return "mini", "", "mini (say your task)"
    if low.startswith("/mini ") or low.startswith("/m "):
        rest = stripped.split(maxsplit=1)[1] if " " in stripped else ""
        return "mini", rest, "mini"

    if re.match(r"^critique\s*:\s*", low):
        rest = re.sub(r"^critique\s*:\s*", "", stripped, flags=re.I)
        return "critique", rest, "critique"

    if low.startswith("/wake"):
        parts = stripped.split()
        count = None
        if len(parts) >= 2 and parts[1].isdigit():
            count = int(parts[1])
        return "wake", "", f"wake({count or 'default'})"

    return "mini", stripped, "mini"


def _run_codex_json_quiet(
    proc: subprocess.Popen[str], *, stop: threading.Event
) -> tuple[str, str, int]:
    """Parse --json stdout; return (final_reply, stderr_tail, exit_code). No terminal streaming."""
    replies: list[str] = []
    stderr_chunks: list[str] = []
    assert proc.stdout is not None

    def _read_stdout() -> None:
        for raw in proc.stdout:
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

    def _read_stderr() -> None:
        if proc.stderr is None:
            return
        stderr_chunks.append(proc.stderr.read() or "")

    out_thread = threading.Thread(target=_read_stdout, daemon=True)
    err_thread = threading.Thread(target=_read_stderr, daemon=True)
    out_thread.start()
    err_thread.start()
    code = proc.wait()
    stop.set()
    out_thread.join(timeout=5)
    err_thread.join(timeout=5)
    final = replies[-1] if replies else ""
    err = "".join(stderr_chunks).strip()
    return final, err, code


def _run_turn(
    codex: str,
    prompt: str,
    *,
    mode: str,
    resume: bool,
    quiet: bool,
) -> int:
    cmd = _base_args(codex, mode=mode)
    use_resume = resume and mode == "mini"
    if use_resume:
        session = _load_session()
        if int(session.get("mini_turns", 0)) >= _max_resume_turns():
            use_resume = False
            print(
                f"(mini context ~full after {_max_resume_turns()} turns — fresh session; /critique refreshes wake_task)",
                flush=True,
            )

    if quiet:
        cmd.append("--json")
    if use_resume:
        cmd.extend(["resume", "--last"])
    cmd.append(prompt)

    model_label = _forced_model() or (_critique_model() if mode == "critique" else _mini_model())
    resume_label = "resume" if use_resume else "new"
    if quiet:
        print(f"\ncodex> [{mode} · {model_label} · {resume_label}] {_prompt_user_preview(prompt, mode=mode)}\n", flush=True)
    else:
        print(f"\n→ [{mode}] model={model_label} {resume_label} …\n", flush=True)

    proc = subprocess.Popen(
        cmd,
        cwd=str(APP_ROOT),
        stdout=subprocess.PIPE if quiet else subprocess.PIPE,
        stderr=subprocess.DEVNULL if quiet else subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    stop_spin = threading.Event()
    spin_thread = None
    if quiet:
        spin_thread = threading.Thread(target=_spinner_until, args=(stop_spin,), daemon=True)
        spin_thread.start()

    reader = None
    if not quiet and proc.stdout:
        reader = threading.Thread(target=_stream_codex_output, args=(proc.stdout,), daemon=True)
        reader.start()

    code = 0
    quiet_reply = ""
    stderr_tail = ""
    try:
        if quiet:
            quiet_reply, stderr_tail, code = _run_codex_json_quiet(proc, stop=stop_spin)
        else:
            code = proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            code = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = 130
        print("\n(interrupted)", flush=True)
    finally:
        stop_spin.set()
        if spin_thread:
            spin_thread.join(timeout=1)
        if reader:
            reader.join(timeout=2)

    if quiet:
        if code == 0 and quiet_reply:
            print(_redact_secrets(quiet_reply), flush=True)
            print(flush=True)
        elif code != 0:
            if stderr_tail:
                print(stderr_tail[-2000:], file=sys.stderr, flush=True)
            print(f"(codex exited {code})", file=sys.stderr, flush=True)
    elif code != 0:
        print(f"(codex exited {code})", file=sys.stderr, flush=True)

    return code


def _print_banner(*, quiet: bool) -> None:
    forced = _forced_model()
    if forced:
        routing = forced
    else:
        routing = f"{_mini_model()} · critique {_critique_model()}"
    mode = "chat only" if quiet else "verbose"
    print(f"vibe12 codex · {routing} · {mode}  (/help · /verbose)")
    print()


def _help() -> None:
    print(
        f"""
Commands:
  /help              This message
  /mini [text]       New mini session ({_mini_model()}) — implementation work
  /critique [text]   New critique session ({_critique_model()}) — checkpoints + memory only
  /c, /m             Short aliases for /critique, /mini
  /new               Next mini turn starts fresh (no resume)
  /bootstrap         Regenerate scratch/memory-bootstrap-latest.md
  /wake [N]          Run vibe12_wake.sh (N minis + critique; default from .env)
  /quiet             Final reply only + spinner (default; uses codex -o)
  /verbose           Full codex stream (file reads, diffs, exec)
  /quit              Exit

CLI: vibe12_codex_tui.py [--verbose|-v] [--quiet|-q]
  Default is quiet (no prompt dump, no tool spam). Orchestration: mini work → /critique queues next slices.

Orchestration (bas_build_spec pattern):
  {_critique_model()} rewrites BUILD_CHECKPOINTS "Next for mini (ordered)"
  {_mini_model()} executes one slice per turn from that queue
  Human notes: cron_codex/state/operator_notes.md → context_since_last_wake.md

Config: {ENV_FILE}  ·  docs: cron_codex/README.md
"""
    )


def _write_bootstrap() -> None:
    cli = SPEC_DIR / "bin" / "vibe12_workspace_cli.sh"
    if not cli.is_file():
        print("missing vibe12_workspace_cli.sh", file=sys.stderr)
        return
    subprocess.run([str(cli), "memory", "write-bootstrap"], check=False, cwd=str(APP_ROOT))


def _parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive Codex REPL for vibe_code_apps_12.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="In-session: /verbose, /quiet, /help, /quit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show full codex exec output (diffs, bash, token stats)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="chat-only output (default unless VIBE12_TUI_QUIET=false)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_cli()
    _load_dotenv(ENV_FILE)
    codex = _codex_bin()
    quiet = _quiet_default(args.verbose, args.quiet)
    _print_banner(quiet=quiet)

    mini_resume = False
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue
        low = line.lower()
        if low in ("/quit", "/exit", "/q"):
            break
        if low == "/help":
            _help()
            continue
        if low == "/new":
            mini_resume = False
            _reset_session()
            print("(fresh Codex session — wake_task + lab_facts only; no resume)")
            continue
        if low == "/quiet":
            quiet = True
            print("(chat-only — use /verbose for diffs and exec)")
            continue
        if low == "/verbose":
            quiet = False
            print("(verbose — full codex stream)")
            continue
        if low == "/bootstrap":
            _write_bootstrap()
            continue

        mode, body, label = _parse_user_line(line)
        if mode == "wake":
            mini_resume = False
            count = None
            if label.startswith("wake(") and label != "wake(default)":
                try:
                    count = int(label[5:-1])
                except ValueError:
                    count = None
            code = _run_orchestrated_wake(count)
            if code != 0:
                print(f"(wake exited {code})", file=sys.stderr)
            continue

        if mode == "critique":
            mini_resume = False
            _reset_session()
            _export_wake_context()
            if label == "critique (template)" or not body.strip():
                prompt = _critique_prompt("")
            else:
                prompt = _critique_prompt(body)
            code = _run_turn(codex, prompt, mode="critique", resume=False, quiet=quiet)
            if code != 0:
                print(f"(critique exited {code})", file=sys.stderr)
            continue

        if label == "mini (say your task)" and not body.strip():
            print("Add a task after /mini, or just type your prompt (uses mini model).")
            continue

        fresh_mini = not mini_resume or label == "mini"
        if fresh_mini:
            _reset_session()
            _export_wake_context()
        prompt = _wrap_mini_prompt(body, fresh=fresh_mini)
        code = _run_turn(codex, prompt, mode="mini", resume=mini_resume and not fresh_mini, quiet=quiet)
        session = _load_session()
        if code == 0:
            mini_resume = True
            session["mini_turns"] = int(session.get("mini_turns", 0)) + 1
            _save_session(session)
        else:
            session["mini_failures"] = int(session.get("mini_failures", 0)) + 1
            _save_session(session)
            print(
                f"(mini exited {code}; /critique to fix wake_task — failures={session['mini_failures']})",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
