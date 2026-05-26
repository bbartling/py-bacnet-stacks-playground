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
BOOTSTRAP = SPEC_DIR / "scratch" / "memory-bootstrap-latest.md"
ENV_FILE = SPEC_DIR / "cron_codex" / ".env"
CRON_BIN = SPEC_DIR / "cron_codex" / "bin"
CONTEXT_SLICE = SPEC_DIR / "cron_codex" / "state" / "context_since_last_wake.md"
WAKE_SCRIPT = CRON_BIN / "vibe12_wake.sh"

MINI_PREAMBLE = """You are working on vibe_code_apps_12 (Vibe12 BACnet → AWS IoT → BRICK/FDD).

Read (do not paste back verbatim):
- vibe12_agent_spec/AGENTS.md
- vibe12_agent_spec/BUILD_CHECKPOINTS.md — **"Next for mini (ordered)"** is your queue (from last critique)
- vibe12_agent_spec/GUARDRAILS.md
- vibe12_agent_spec/cron_codex/state/context_since_last_wake.md
- vibe12_agent_spec/memory/commissioning/PHASE_NOTEPAD.md

Do ONE slice from **Next for mini (ordered)** only. Skills: vibe12_agent_spec/skills/.
Humans own SSH and points.csv. Run ./scripts/validate_cloud_pipeline.sh before claiming cloud OK.
Never read or grep aws_cloud_pipeline/samconfig.toml (secrets) — use WEB_PASSWORD env for validate scripts.

User request:
"""

CRITIQUE_PROMPT_TEMPLATE = """You are the CRITIQUE pass ({critique_model}) on vibe_code_apps_12.
Do not implement features — orchestrate the next minis.

Read:
- vibe12_agent_spec/AGENTS.md, BUILD_CHECKPOINTS.md, GUARDRAILS.md, MEMORY.md
- vibe12_agent_spec/memory/{today}.md
- vibe12_agent_spec/cron_codex/state/context_since_last_wake.md
- vibe12_agent_spec/cron_codex/state/next_directions.md
- vibe12_agent_spec/memory/commissioning/PHASE_NOTEPAD.md

Tasks:
1) Critique what changed (git diff, Done recently, validate_cloud_pipeline if cloud touched).
2) Rewrite BUILD_CHECKPOINTS: **Last critique ({critique_model})**, **Current sprint**, **Next for mini (ordered)** (3–8 specific tasks for {mini_model}).
3) Optionally refresh cron_codex/state/next_directions.md for long-form paste context.
4) Append summary to memory/{today}.md; promote to MEMORY.md when durable.
5) Confirm minis would honor operator notes + PHASE_NOTEPAD.

**Next for mini (ordered)** is the canonical queue — minis must execute it without re-planning the project.

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


def _is_exec_noise(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if s == "exec":
        return True
    if s.startswith("/bin/bash") or s.startswith("bash -lc"):
        return True
    if " succeeded in " in line:
        return True
    if re.match(r"^in [/~]", s):
        return True
    if re.match(r"^\d+\|", s) and _SECRET_LINE.search(line):
        return True
    return False


def _quiet_default() -> bool:
    val = os.environ.get("VIBE12_TUI_QUIET", "true").strip().lower()
    return val not in ("0", "false", "no", "off")


def _stream_codex_output(pipe, *, quiet: bool) -> None:
    """Forward codex stdout; in quiet mode hide exec/tool lines, show assistant text only."""
    mode = "pass"
    try:
        for raw in iter(pipe.readline, ""):
            line = raw.rstrip("\n")
            if not quiet:
                print(_redact_secrets(line), flush=True)
                continue

            s = line.strip()
            if s == "exec":
                mode = "suppress"
                continue
            if s == "codex" or s.lower().startswith("codex "):
                mode = "assistant"
                if s.lower().startswith("codex ") and len(s) > 5:
                    print(_redact_secrets(line), flush=True)
                continue
            if mode == "suppress":
                continue
            if _is_exec_noise(line):
                continue
            print(_redact_secrets(line), flush=True)
    finally:
        pipe.close()


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
    parts = [MINI_PREAMBLE, text.strip()]
    if BOOTSTRAP.is_file():
        snippet = BOOTSTRAP.read_text(encoding="utf-8", errors="replace")
        if len(snippet) > 4000:
            snippet = snippet[:4000] + "\n…(bootstrap truncated)\n"
        parts.insert(
            1,
            "\n--- memory bootstrap (summary) ---\n" + snippet + "\n--- end bootstrap ---\n",
        )
    return "\n".join(parts)


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


def _run_turn(
    codex: str,
    prompt: str,
    *,
    mode: str,
    resume: bool,
    quiet: bool,
) -> int:
    cmd = _base_args(codex, mode=mode)
    if resume and mode == "mini":
        cmd.extend(["resume", "--last"])
    cmd.append(prompt)

    model_label = _forced_model() or (_critique_model() if mode == "critique" else _mini_model())
    resume_label = "resume" if resume and mode == "mini" else "new"
    if quiet:
        print(f"\n→ [{mode}] {model_label} ({resume_label}) — quiet mode (hide exec noise)\n", flush=True)
    else:
        print(f"\n→ [{mode}] model={model_label} {resume_label} …\n", flush=True)

    proc = subprocess.Popen(
        cmd,
        cwd=str(APP_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    stop_spin = threading.Event()
    spin_thread = None
    if quiet and proc.stdout:
        spin_thread = threading.Thread(target=_spinner_until, args=(stop_spin,), daemon=True)
        spin_thread.start()

    reader = None
    if proc.stdout:
        reader = threading.Thread(
            target=_stream_codex_output,
            args=(proc.stdout,),
            kwargs={"quiet": quiet},
            daemon=True,
        )
        reader.start()

    try:
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

    if quiet and code == 0:
        print("(done)\n", flush=True)
    return code


def _print_banner() -> None:
    _, sandbox_label = _sandbox_args()
    forced = _forced_model()
    if forced:
        routing = f"forced model: {forced}"
    else:
        routing = f"mini={_mini_model()}  critique={_critique_model()}"
    print("vibe12 codex tui — type a prompt and press Enter")
    print(f"  workspace: {APP_ROOT}")
    print(f"  routing: {routing}")
    print(f"  sandbox: {sandbox_label}")
    print("  commands: /help  /mini  /critique  /wake [N]  /new  /verbose  /quiet  /quit")
    print(f"  output:   {'quiet (exec hidden, spinner)' if _quiet_default() else 'verbose (all codex output)'}")
    print("  flow:     critique sets Next for mini → minis consume that queue")
    print("  prefix:   critique: <notes>  → gpt-5.5 only")
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
  /quiet             Hide exec/tool noise; spinner + Codex replies only (default)
  /verbose           Show full codex exec stream (debug)
  /quit              Exit

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


def main() -> int:
    _load_dotenv(ENV_FILE)
    codex = _codex_bin()
    _print_banner()

    mini_resume = False
    quiet = _quiet_default()
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
            print("(next mini turn starts a new Codex session)")
            continue
        if low == "/quiet":
            quiet = True
            print("(quiet mode — exec hidden, spinner on)")
            continue
        if low == "/verbose":
            quiet = False
            print("(verbose mode — full codex output)")
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
            _export_wake_context()
        prompt = _wrap_mini_prompt(body, fresh=fresh_mini)
        code = _run_turn(codex, prompt, mode="mini", resume=mini_resume and not fresh_mini, quiet=quiet)
        if code == 0:
            mini_resume = True
        else:
            print(f"(mini exited {code}; /new for fresh session)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
