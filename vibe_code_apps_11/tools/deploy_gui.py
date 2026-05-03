#!/usr/bin/env python3
"""
Tkinter GUI: edit local .env, configure Pi deploy options.

There is only one Windows deploy driver: deploy_to_pi.ps1 at the repo root (next to the tools/
folder). The GUI builds the same powershell.exe -File ... argument list you would run manually
from the diy-bas directory. On macOS/Linux it runs tools/deploy_via_ssh.py instead.

Run Deploy merges the top-bar Integrator / Building Operator fields into the .env editor and
saves the current env file path before starting (same as "Write these logins into .env tab").
deploy_to_pi.ps1 then writes the same Integrator / Building Operator values into the Pi's .env
(after optional sync from .env.example) so browser login matches the GUI without uploading .env
in the zip.

If **DIY_BAS_NTFY_ALLOWED** is checked on the ntfy tab, Run Deploy also merges DIY_BAS_NTFY_* into
local .env and pushes those keys to the Pi (apply_ntfy_env_from_stdin.py) so the running app can
use ntfy after compose comes up.
"""
from __future__ import annotations

import base64
import json
import os
import queue
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import BOTH, END, LEFT, NW, TOP, W, X, scrolledtext, ttk, messagebox, filedialog

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
STATE_PATH = Path.home() / ".diy-bas-deploy-gui.json"

_NTFY_STATE_KEYS = (
    "ntfy_allowed",
    "ntfy_url",
    "ntfy_topic",
    "ntfy_username",
    "ntfy_password",
    "ntfy_test_title",
    "ntfy_test_priority",
    "ntfy_test_tags",
    "ntfy_test_message",
)


def _ntfy_send_raw(
    *,
    base_url: str,
    topic: str,
    title: str,
    priority: str,
    tags: str,
    message: str,
    username: str,
    password: str,
    timeout_sec: int = 20,
) -> str:
    """POST to ntfy (same as PowerShell Invoke-RestMethod to https://ntfy.sh/$Topic). Returns response body snippet."""
    from urllib.error import HTTPError, URLError
    from urllib.parse import quote
    from urllib.request import Request, urlopen

    base = (base_url or "https://ntfy.sh").strip().rstrip("/")
    t = (topic or "").strip()
    if not t:
        raise ValueError("Topic is empty")
    url = f"{base}/{quote(t, safe='')}"
    req = Request(url, data=(message or " ").encode("utf-8"), method="POST")
    req.add_header("Title", (title or "diy-bas")[:200])
    req.add_header("Priority", (priority or "default")[:20])
    if (tags or "").strip():
        req.add_header("Tags", tags.strip()[:200])
    user = (username or "").strip()
    if user:
        token = base64.b64encode(f"{user}:{password or ''}".encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {token}")
    to = max(5, min(60, int(timeout_sec)))
    try:
        with urlopen(req, timeout=to) as resp:
            return (resp.read() or b"").decode("utf-8", errors="replace")[:4000]
    except HTTPError as e:
        body = (e.read() or b"").decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"HTTP {e.code}: {body or e.reason}") from e
    except URLError as e:
        raise RuntimeError(str(e.reason or e)) from e


# Larger defaults for field techs / small laptop screens
_DEFAULT_UI_FONT = ("Segoe UI", 12)
_DEFAULT_TEXT_SIZE_PT = 20
_DEFAULT_LOG_FONT_WIN = ("Consolas", _DEFAULT_TEXT_SIZE_PT)
_DEFAULT_LOG_FONT_UNIX = ("Menlo", _DEFAULT_TEXT_SIZE_PT)


def _ps_bool_arg(b: bool) -> str:
    """deploy_to_pi.ps1 uses [int] 0/1 for switch-like params (reliable from Python/subprocess)."""
    return "1" if b else "0"


def _expand_pi_placeholders(path: str, pi_user: str) -> str:
    """Replace <user> in saved paths (e.g. /home/<user>/diy-bacnet-server) with the real SSH username."""
    p = (path or "").strip()
    if not p:
        return ""
    return p.replace("<user>", pi_user).replace("<USER>", pi_user)


def parse_env_text(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            out[k] = v
    return out


def merge_env_lines(text: str, updates: dict[str, str]) -> str:
    """Replace existing KEY=value lines (case-insensitive key match) or append missing keys."""
    if not updates:
        return text
    key_by_upper = {k.upper(): k for k in updates}
    seen: set[str] = set()
    out: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(raw)
            continue
        key_part, _, _val = stripped.partition("=")
        key = key_part.strip()
        lu = key.upper()
        if lu in key_by_upper:
            canon = key_by_upper[lu]
            out.append(f"{canon}={updates[canon]}")
            seen.add(canon)
        else:
            out.append(raw)
    missing = [f"{k}={v}" for k, v in updates.items() if k not in seen]
    if missing:
        if out and out[-1].strip():
            out.append("")
        out.extend(missing)
    return "\n".join(out) + ("\n" if out else "")


def build_powershell_argv(cfg: dict) -> list[str]:
    """Argv for: powershell.exe -File deploy_to_pi.ps1 ..."""
    ps1 = ROOT / "deploy_to_pi.ps1"
    args: list[str] = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps1),
        "-PiHost",
        cfg["pi_host"].strip(),
        "-PiUser",
        cfg["pi_user"].strip(),
    ]
    pi_u = cfg["pi_user"].strip()
    rd = _expand_pi_placeholders(cfg.get("remote_dir") or "", pi_u)
    if rd:
        args.extend(["-RemoteDir", rd])
    rbd = _expand_pi_placeholders(cfg.get("remote_bacnet_dir") or "", pi_u)
    if rbd:
        args.extend(["-RemoteBacnetDir", rbd])
    args.extend(["-RunBootstrap", _ps_bool_arg(bool(cfg.get("run_bootstrap")))])
    args.extend(["-StartApp", _ps_bool_arg(bool(cfg.get("start_app")))])
    args.extend(["-UseDockerStack", _ps_bool_arg(bool(cfg.get("use_docker_stack")))])
    args.extend(["-TestLogin", _ps_bool_arg(bool(cfg.get("test_login")))])
    args.extend(
        ["-SyncBootstrapCredentialsFromExample", _ps_bool_arg(bool(cfg.get("sync_bootstrap_credentials")))]
    )
    args.extend(["-DockerMaintenance", _ps_bool_arg(bool(cfg.get("docker_maintenance")))])
    args.extend(["-LoginUsername", (cfg.get("login_username") or "integrator").strip()])
    args.extend(["-LoginPassword", cfg.get("login_password") or ""])
    args.extend(["-MaintUsername", (cfg.get("maint_username") or "maintenance").strip()])
    args.extend(["-MaintPassword", cfg.get("maint_password") or ""])
    args.extend(["-VerboseDeploy", _ps_bool_arg(bool(cfg.get("verbose_deploy")))])
    args.extend(["-BootstrapLogTail", str(int(cfg.get("bootstrap_log_tail") or 80))])
    args.extend(["-ComposeLogTail", str(int(cfg.get("compose_log_tail") or 50))])
    if cfg.get("ntfy_push") and cfg.get("ntfy_env_for_pi"):
        ntfy_obj = cfg["ntfy_env_for_pi"]
        if isinstance(ntfy_obj, dict) and ntfy_obj:
            njson = json.dumps(ntfy_obj, separators=(",", ":"))
            nb64 = base64.b64encode(njson.encode("utf-8")).decode("ascii")
            args.extend(["-NtfyPush", "1", "-NtfyEnvB64", nb64])
        else:
            args.extend(["-NtfyPush", "0", "-NtfyEnvB64", ""])
    else:
        args.extend(["-NtfyPush", "0", "-NtfyEnvB64", ""])
    return args


def build_python_ssh_argv(cfg: dict) -> list[str]:
    """Argv for: python tools/deploy_via_ssh.py ..."""
    script = TOOLS / "deploy_via_ssh.py"
    args: list[str] = [sys.executable, str(script), "--pi-host", cfg["pi_host"].strip(), "--pi-user", cfg["pi_user"].strip()]
    pi_u = cfg["pi_user"].strip()
    rd = _expand_pi_placeholders(cfg.get("remote_dir") or "", pi_u)
    if rd:
        args.extend(["--remote-dir", rd])
    rbd = _expand_pi_placeholders(cfg.get("remote_bacnet_dir") or "", pi_u)
    if rbd:
        args.extend(["--remote-bacnet-dir", rbd])
    if not cfg.get("run_bootstrap"):
        args.append("--no-run-bootstrap")
    if not cfg.get("start_app"):
        args.append("--no-start-app")
    if not cfg.get("use_docker_stack"):
        args.append("--no-docker-stack")
    if not cfg.get("test_login"):
        args.append("--no-test-login")
    if not cfg.get("sync_bootstrap_credentials"):
        args.append("--no-sync-bootstrap-credentials")
    if not cfg.get("docker_maintenance"):
        args.append("--no-docker-maintenance")
    args.extend(["--login-username", (cfg.get("login_username") or "integrator").strip()])
    args.extend(["--login-password", cfg.get("login_password") or ""])
    args.extend(["--maint-username", (cfg.get("maint_username") or "maintenance").strip()])
    args.extend(["--maint-password", cfg.get("maint_password") or ""])
    if cfg.get("verbose_deploy"):
        args.append("--verbose-deploy")
    args.extend(["--bootstrap-log-tail", str(int(cfg.get("bootstrap_log_tail") or 80))])
    args.extend(["--compose-log-tail", str(int(cfg.get("compose_log_tail") or 50))])
    if cfg.get("ntfy_push") and cfg.get("ntfy_env_for_pi"):
        ntfy_obj = cfg["ntfy_env_for_pi"]
        if isinstance(ntfy_obj, dict) and ntfy_obj:
            nb64 = base64.b64encode(json.dumps(ntfy_obj, separators=(",", ":")).encode("utf-8")).decode("ascii")
            args.append("--ntfy-push")
            args.extend(["--ntfy-env-b64", nb64])
    return args


class DeployGuiApp:
    def __init__(self) -> None:
        import tkinter as tk

        self.tk = tk
        self.root = tk.Tk()
        self.root.title("DIY-BAS — deploy to Pi")
        self.root.geometry("960x720")
        self.root.minsize(760, 520)

        self.log_q: queue.Queue[str | None] = queue.Queue()
        self._proc: subprocess.Popen[str] | None = None
        self._console_busy = False
        self._form_font_widgets: list = []

        style = ttk.Style()
        style.configure("TLabel", font=_DEFAULT_UI_FONT)
        style.configure("TButton", font=_DEFAULT_UI_FONT)
        style.configure("TCheckbutton", font=_DEFAULT_UI_FONT)
        style.configure("TRadiobutton", font=_DEFAULT_UI_FONT)
        style.configure("TLabelframe.Label", font=_DEFAULT_UI_FONT)
        style.configure("TNotebook.Tab", font=_DEFAULT_UI_FONT, padding=(10, 4))

        self._build_top_bar()

        nb = ttk.Notebook(self.root)
        nb.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))

        self.tab_deploy = ttk.Frame(nb, padding=6)
        self.tab_env = ttk.Frame(nb, padding=6)
        self.tab_ntfy = ttk.Frame(nb, padding=6)
        nb.add(self.tab_deploy, text="Deploy to Pi")
        nb.add(self.tab_env, text=".env editor (app settings)")
        nb.add(self.tab_ntfy, text="ntfy (push)")

        self._build_deploy_tab()
        self._build_env_tab()
        self._build_ntfy_tab()
        self._apply_fonts()
        self._load_state()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(200, self._drain_log_queue)

    def _mono_family(self) -> str:
        return "Consolas" if sys.platform == "win32" else "Menlo"

    def _form_entry(self, master, **kw) -> object:
        """tk.Entry so Windows honors font size; same family/size as console/.env."""
        w = self.tk.Entry(
            master,
            font=(self._mono_family(), _DEFAULT_TEXT_SIZE_PT),
            relief=self.tk.SOLID,
            bd=1,
            **kw,
        )
        self._form_font_widgets.append(w)
        return w

    def _form_spinbox(self, master, **kw) -> object:
        w = self.tk.Spinbox(
            master,
            font=(self._mono_family(), _DEFAULT_TEXT_SIZE_PT),
            **kw,
        )
        self._form_font_widgets.append(w)
        return w

    def _build_top_bar(self) -> None:
        tk = self.tk
        top = ttk.Frame(self.root, padding=(8, 6))
        top.pack(fill=X, side=TOP)

        row_font = ttk.Frame(top)
        row_font.pack(fill=X)
        ttk.Label(row_font, text="Text size").pack(side=LEFT, padx=(0, 6))
        self.var_font_pt = tk.IntVar(value=_DEFAULT_TEXT_SIZE_PT)
        self.sp_font = self._form_spinbox(
            row_font,
            from_=10,
            to=24,
            width=5,
            textvariable=self.var_font_pt,
            command=self._apply_fonts,
        )
        self.sp_font.pack(side=LEFT, padx=(0, 6))
        ttk.Label(row_font, text="pt").pack(side=LEFT)
        self.var_font_pt.trace_add("write", lambda *_: self._apply_fonts())

        lf = ttk.LabelFrame(
            top,
            text="Logins (same as .env — integrator is used to test the site after deploy)",
            padding=8,
        )
        lf.pack(fill=X, pady=(8, 0))
        ttk.Label(lf, text="").grid(row=0, column=0, sticky=W)
        ttk.Label(lf, text="User name").grid(row=0, column=1, sticky=W, pady=(0, 2))
        ttk.Label(lf, text="Password").grid(row=0, column=2, sticky=W, padx=(12, 0), pady=(0, 2))
        ttk.Label(lf, text="Integrator").grid(row=1, column=0, sticky=W, padx=(0, 8), pady=4)
        self.var_login_user = self._form_entry(lf, width=22)
        self.var_login_user.grid(row=1, column=1, sticky="ew", pady=4)
        self.var_login_pass = self._form_entry(lf, width=20)
        self.var_login_pass.grid(row=1, column=2, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(lf, text="Building Operator").grid(row=2, column=0, sticky=W, padx=(0, 8), pady=4)
        self.var_maint_user = self._form_entry(lf, width=22)
        self.var_maint_user.grid(row=2, column=1, sticky="ew", pady=4)
        self.var_maint_pass = self._form_entry(lf, width=20)
        self.var_maint_pass.grid(row=2, column=2, sticky="ew", padx=(12, 0), pady=4)
        lf.columnconfigure(1, weight=1)
        lf.columnconfigure(2, weight=1)

        ttk.Button(top, text="Write these logins into .env tab", command=self._push_logins_to_env_tab).pack(
            anchor=W, pady=(6, 0)
        )

    def _apply_fonts(self) -> None:
        try:
            pt = int(self.var_font_pt.get())
        except (self.tk.TclError, ValueError, TypeError):
            pt = _DEFAULT_TEXT_SIZE_PT
        pt = max(10, min(24, pt))
        body_pt = max(10, pt - 1)
        body_family = "Segoe UI" if sys.platform == "win32" else "Helvetica"
        body = (body_family, body_pt)
        style = ttk.Style()
        style.configure("TLabel", font=body)
        style.configure("TButton", font=body)
        style.configure("TCheckbutton", font=body)
        style.configure("TRadiobutton", font=body)
        style.configure("TLabelframe.Label", font=body)
        style.configure("TNotebook.Tab", font=body, padding=(10, 4))

        mono = (self._mono_family(), pt)
        for w in self._form_font_widgets:
            try:
                w.configure(font=mono)
            except self.tk.TclError:
                pass
        if getattr(self, "txt_log", None):
            self.txt_log.configure(font=mono)
        if getattr(self, "txt_env", None):
            self.txt_env.configure(font=mono)
        if getattr(self, "_deploy_title", None):
            tpt = max(14, min(24, pt + 2))
            self._deploy_title.configure(font=("Segoe UI", tpt, "bold"))
        if getattr(self, "btn_run", None):
            self.btn_run.configure(font=("Segoe UI", max(12, min(20, pt - 2)), "bold"))

    def _on_advanced_toggle(self) -> None:
        if self.v_show_advanced.get():
            self.frm_advanced.grid(row=self._advanced_row, column=0, columnspan=2, sticky="ew", pady=4)
        else:
            self.frm_advanced.grid_remove()

    def _build_deploy_tab(self) -> None:
        f = self.tab_deploy
        tk = self.tk
        row = 0

        self._deploy_title = tk.Label(
            f,
            text="Deploy DIY-BAS to your Raspberry Pi",
            font=("Segoe UI", 16, "bold"),
            fg="#1a1a2e",
        )
        self._deploy_title.grid(row=row, column=0, columnspan=2, sticky=W, pady=(0, 10))
        row += 1

        def add_row(label: str, widget) -> None:
            nonlocal row
            ttk.Label(f, text=label).grid(row=row, column=0, sticky=W, pady=4, padx=(0, 8))
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            f.columnconfigure(1, weight=1)
            row += 1

        self.var_pi_host = self._form_entry(f, width=42)
        self.var_pi_user = self._form_entry(f, width=22)
        add_row("Pi address (IP or name)", self.var_pi_host)
        add_row("Pi login name (SSH user)", self.var_pi_user)
        self.var_ssh_pass = self._form_entry(f, width=40)
        add_row("SSH password (optional — leave blank if you use keys only)", self.var_ssh_pass)

        tip_login = tk.Label(
            f,
            text='Integrator and Building Operator logins: use the bar at the top (and "Write … into .env tab").',
            font=("Segoe UI", 10),
            fg="#444",
            wraplength=860,
            justify=LEFT,
        )
        tip_login.grid(row=row, column=0, columnspan=2, sticky=W, pady=(0, 4))
        row += 1

        btn_row = ttk.Frame(f)
        btn_row.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1
        self.btn_run = tk.Button(
            btn_row,
            text="  RUN DEPLOY  ",
            command=self._run_deploy,
            bg="#0b57d0",
            fg="white",
            activebackground="#0842a0",
            activeforeground="white",
            font=("Segoe UI", 14, "bold"),
            padx=20,
            pady=12,
            cursor="hand2",
            relief=tk.FLAT,
        )
        self.btn_run.pack(side=LEFT, padx=(0, 12))
        ttk.Button(btn_row, text="Check SSH", command=self._check_ssh).pack(side=LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="Copy output", command=self._copy_output).pack(side=LEFT, padx=(0, 8))

        tip = tk.Label(
            f,
            text=(
                "Settings save automatically when you run deploy or close this window. "
                "Use the \".env editor\" tab for app secrets; open \"Show extra options\" for folders and Docker steps."
            ),
            font=("Segoe UI", 10),
            fg="#444",
            wraplength=880,
            justify=LEFT,
        )
        tip.grid(row=row, column=0, columnspan=2, sticky=W, pady=(0, 6))
        row += 1

        self.v_show_advanced = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f,
            text="Show extra options (folders, Docker steps, copy command, …)",
            variable=self.v_show_advanced,
            command=self._on_advanced_toggle,
        ).grid(row=row, column=0, columnspan=2, sticky=W, pady=2)
        row += 1

        self.frm_advanced = ttk.Frame(f)
        self._advanced_row = row

        adv = self.frm_advanced
        ar = 0

        def add_adv_row(label: str, widget) -> None:
            nonlocal ar
            ttk.Label(adv, text=label).grid(row=ar, column=0, sticky=W, pady=2, padx=(0, 8))
            widget.grid(row=ar, column=1, sticky="ew", pady=2)
            adv.columnconfigure(1, weight=1)
            ar += 1

        self.var_remote_dir = self._form_entry(adv, width=52)
        self.var_remote_bacnet = self._form_entry(adv, width=52)
        add_adv_row("App folder on Pi (leave blank for default)", self.var_remote_dir)
        add_adv_row("BACnet server folder on Pi", self.var_remote_bacnet)

        opts = ttk.LabelFrame(adv, text="Deploy steps (defaults are ON — normal full deploy)", padding=8)
        opts.grid(row=ar, column=0, columnspan=2, sticky="ew", pady=8)
        ar += 1

        self.v_run_bootstrap = tk.BooleanVar(value=True)
        self.v_start_app = tk.BooleanVar(value=True)
        self.v_docker_stack = tk.BooleanVar(value=True)
        self.v_test_login = tk.BooleanVar(value=True)
        self.v_sync_bootstrap = tk.BooleanVar(value=True)
        self.v_docker_maint = tk.BooleanVar(value=True)
        self.v_verbose = tk.BooleanVar(value=False)
        self.chk_run_bootstrap = ttk.Checkbutton(
            opts, text="Run first-time setup (bootstrap)", variable=self.v_run_bootstrap
        )
        self.chk_start_app = ttk.Checkbutton(opts, text="Start Docker app after copy", variable=self.v_start_app)
        self.chk_docker_stack = ttk.Checkbutton(
            opts, text="Use full Docker stack (Caddy + diy-bas)", variable=self.v_docker_stack
        )
        self.chk_test_login = ttk.Checkbutton(opts, text="Test DIY BAS login after deploy", variable=self.v_test_login)
        self.chk_sync_bootstrap = ttk.Checkbutton(
            opts, text="Sync bootstrap passwords from .env.example on Pi", variable=self.v_sync_bootstrap
        )
        self.chk_docker_maint = ttk.Checkbutton(
            opts, text="Clean up old Docker backups on Pi", variable=self.v_docker_maint
        )
        self.chk_verbose = ttk.Checkbutton(
            opts, text="Verbose Docker build (more detail in logs)", variable=self.v_verbose
        )
        for i, w in enumerate(
            [
                self.chk_run_bootstrap,
                self.chk_start_app,
                self.chk_docker_stack,
                self.chk_test_login,
                self.chk_sync_bootstrap,
                self.chk_docker_maint,
                self.chk_verbose,
            ]
        ):
            w.grid(row=i // 2, column=i % 2, sticky=W, padx=4, pady=2)

        tail = ttk.Frame(adv)
        tail.grid(row=ar, column=0, columnspan=2, sticky=W, pady=6)
        ar += 1
        ttk.Label(tail, text="Bootstrap log lines").pack(side=LEFT)
        self.var_boot_tail = self._form_spinbox(tail, from_=10, to=500, width=7)
        self.var_boot_tail.pack(side=LEFT, padx=(6, 24))
        ttk.Label(tail, text="Compose log lines").pack(side=LEFT)
        self.var_compose_tail = self._form_spinbox(tail, from_=10, to=500, width=7)
        self.var_compose_tail.pack(side=LEFT, padx=6)

        adv_hint = (
            "Windows: runs only the repo-root deploy_to_pi.ps1 (nothing under tools/ duplicates it). "
            "Mac/Linux: uses tools/deploy_via_ssh.py. "
            "SSH check: blank SSH password uses keys; with a password, Windows needs PuTTY "
            "`plink` in PATH, Mac/Linux needs `sshpass`."
        )
        ttk.Label(adv, text=adv_hint, wraplength=860).grid(row=ar, column=0, columnspan=2, sticky=W, pady=6)
        ar += 1

        adv_btns = ttk.Frame(adv)
        adv_btns.grid(row=ar, column=0, columnspan=2, sticky=W, pady=6)
        ar += 1
        ttk.Button(adv_btns, text="Pull names from .env tab", command=self._fill_from_env_tab).pack(side=LEFT, padx=(0, 8))
        ttk.Button(adv_btns, text="Save settings now", command=self._save_state).pack(side=LEFT, padx=(0, 8))
        ttk.Button(adv_btns, text="Copy deploy command", command=self._copy_cmd).pack(side=LEFT)

        log_row = self._advanced_row + 1
        logf = ttk.LabelFrame(f, text="Console output", padding=6)
        logf.grid(row=log_row, column=0, columnspan=2, sticky="nsew", pady=8)
        f.rowconfigure(log_row, weight=1)
        f.columnconfigure(0, weight=1)
        mono = _DEFAULT_LOG_FONT_WIN if sys.platform == "win32" else _DEFAULT_LOG_FONT_UNIX
        self.txt_log = scrolledtext.ScrolledText(logf, height=12, wrap="word", font=mono)
        self.txt_log.pack(fill=BOTH, expand=True)

        self.frm_advanced.grid_remove()

    def _build_env_tab(self) -> None:
        f = self.tab_env
        tk = self.tk
        hint = tk.Label(
            f,
            text="This file holds passwords and URLs for the app. Use \"Text size\" at the top of the window to enlarge text.",
            font=("Segoe UI", 10),
            fg="#444",
            wraplength=860,
            justify=LEFT,
        )
        hint.pack(anchor=W, pady=(0, 6))
        bar = ttk.Frame(f)
        bar.pack(fill=X, pady=(0, 6))
        ttk.Button(bar, text="Load .env", command=self._load_env_file).pack(side=LEFT, padx=(0, 6))
        ttk.Button(bar, text="Load .env.example", command=self._load_env_example).pack(side=LEFT, padx=(0, 6))
        ttk.Button(bar, text="Save .env", command=self._save_env_file).pack(side=LEFT, padx=(0, 6))
        ttk.Button(bar, text="Open other…", command=self._open_env_other).pack(side=LEFT, padx=(0, 6))
        ttk.Button(bar, text="Send to Deploy tab", command=self._fill_from_env_tab).pack(side=LEFT)

        mono0 = _DEFAULT_LOG_FONT_WIN if sys.platform == "win32" else _DEFAULT_LOG_FONT_UNIX
        self.txt_env = scrolledtext.ScrolledText(f, wrap="none", font=mono0)
        self.txt_env.pack(fill=BOTH, expand=True)
        self._env_path = ROOT / ".env"
        self._load_env_path(self._env_path, silent=True)

    def _build_ntfy_tab(self) -> None:
        f = self.tab_ntfy
        tk = self.tk
        intro = tk.Label(
            f,
            text=(
                "Check DIY_BAS_NTFY_ALLOWED, fill URL and topic, then use Run Deploy on the first tab: "
                "the GUI merges these keys into your local .env and pushes the same values to the Pi "
                "after upload (no extra merge button). Send test push tries ntfy from this PC only."
            ),
            font=("Segoe UI", 10),
            fg="#444",
            wraplength=880,
            justify=LEFT,
        )
        intro.pack(anchor=W, pady=(0, 10))

        form = ttk.LabelFrame(f, text="ntfy → .env and Pi on deploy", padding=10)
        form.pack(fill=X, pady=(0, 10))
        self.v_ntfy_allowed = tk.BooleanVar(value=False)
        r = 0

        def add_nf(row: int, label: str, widget) -> int:
            ttk.Label(form, text=label).grid(row=row, column=0, sticky=W, padx=(0, 10), pady=4)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            form.columnconfigure(1, weight=1)
            return row + 1

        r = add_nf(
            r,
            "Allow ntfy",
            ttk.Checkbutton(form, text="DIY_BAS_NTFY_ALLOWED (merge + push on Run Deploy)", variable=self.v_ntfy_allowed),
        )
        self.var_ntfy_url = self._form_entry(form, width=56)
        r = add_nf(r, "Base URL", self.var_ntfy_url)
        self.var_ntfy_topic = self._form_entry(form, width=40)
        r = add_nf(r, "Topic", self.var_ntfy_topic)
        self.var_ntfy_username = self._form_entry(form, width=28)
        r = add_nf(r, "HTTP Basic user (optional)", self.var_ntfy_username)
        self.var_ntfy_password = self._form_entry(form, width=28)
        r = add_nf(r, "HTTP Basic password", self.var_ntfy_password)

        testf = ttk.LabelFrame(f, text="Test push from this PC", padding=10)
        testf.pack(fill=X, pady=(0, 10))
        self.var_ntfy_test_title = self._form_entry(testf, width=40)
        ttk.Label(testf, text="Title").grid(row=0, column=0, sticky=W, padx=(0, 8), pady=4)
        self.var_ntfy_test_title.grid(row=0, column=1, sticky="ew", pady=4)
        self.cb_ntfy_priority = ttk.Combobox(
            testf,
            width=14,
            state="readonly",
            values=("min", "low", "default", "high", "max", "1", "2", "3", "4", "5"),
        )
        self.cb_ntfy_priority.set("high")
        ttk.Label(testf, text="Priority").grid(row=1, column=0, sticky=W, padx=(0, 8), pady=4)
        self.cb_ntfy_priority.grid(row=1, column=1, sticky=W, pady=4)
        self.var_ntfy_test_tags = self._form_entry(testf, width=24)
        ttk.Label(testf, text="Tags").grid(row=2, column=0, sticky=W, padx=(0, 8), pady=4)
        self.var_ntfy_test_tags.grid(row=2, column=1, sticky="ew", pady=4)
        self.txt_ntfy_msg = scrolledtext.ScrolledText(
            testf, height=3, width=60, font=(self._mono_family(), max(10, _DEFAULT_TEXT_SIZE_PT - 2))
        )
        ttk.Label(testf, text="Message").grid(row=3, column=0, sticky=NW, padx=(0, 8), pady=4)
        self.txt_ntfy_msg.grid(row=3, column=1, sticky="ew", pady=4)
        testf.columnconfigure(1, weight=1)

        act = ttk.Frame(f)
        act.pack(fill=X, pady=(0, 6))
        ttk.Button(act, text="Send test push", command=self._on_ntfy_test_click).pack(side=LEFT, padx=(0, 8))
        ttk.Button(act, text="Save .env", command=self._save_env_file).pack(side=LEFT)

    def _ntfy_default_state(self) -> dict:
        return {
            "ntfy_allowed": False,
            "ntfy_url": "https://ntfy.sh",
            "ntfy_topic": "bens-bas-test-alerts",
            "ntfy_username": "",
            "ntfy_password": "",
            "ntfy_test_title": "BAS Alarm",
            "ntfy_test_priority": "high",
            "ntfy_test_tags": "warning",
            "ntfy_test_message": "AHU-1 supply fan failed to start. (deploy GUI test)",
        }

    def _apply_ntfy_gui_state(self, d: dict) -> None:
        def set_entry(w, v: str) -> None:
            w.delete(0, END)
            w.insert(0, v)

        allowed = d.get("ntfy_allowed", d.get("ntfy_enabled", False))
        self.v_ntfy_allowed.set(bool(allowed))
        set_entry(self.var_ntfy_url, str(d.get("ntfy_url", "https://ntfy.sh")))
        set_entry(self.var_ntfy_topic, str(d.get("ntfy_topic", "")))
        set_entry(self.var_ntfy_username, str(d.get("ntfy_username", "")))
        set_entry(self.var_ntfy_password, str(d.get("ntfy_password", "")))
        set_entry(self.var_ntfy_test_title, str(d.get("ntfy_test_title", "BAS Alarm")))
        pr = str(d.get("ntfy_test_priority", "high"))
        if pr in ("min", "low", "default", "high", "max", "1", "2", "3", "4", "5"):
            self.cb_ntfy_priority.set(pr)
        else:
            self.cb_ntfy_priority.set("high")
        set_entry(self.var_ntfy_test_tags, str(d.get("ntfy_test_tags", "warning")))
        self.txt_ntfy_msg.delete("1.0", END)
        self.txt_ntfy_msg.insert("1.0", str(d.get("ntfy_test_message", "")))

    def _ntfy_collect_gui_dict(self) -> dict[str, object]:
        return {
            "ntfy_allowed": self.v_ntfy_allowed.get(),
            "ntfy_url": self.var_ntfy_url.get(),
            "ntfy_topic": self.var_ntfy_topic.get(),
            "ntfy_username": self.var_ntfy_username.get(),
            "ntfy_password": self.var_ntfy_password.get(),
            "ntfy_test_title": self.var_ntfy_test_title.get(),
            "ntfy_test_priority": self.cb_ntfy_priority.get(),
            "ntfy_test_tags": self.var_ntfy_test_tags.get(),
            "ntfy_test_message": self.txt_ntfy_msg.get("1.0", END).rstrip("\n"),
        }

    def _ntfy_env_updates_from_gui(self) -> dict[str, str]:
        g = self._ntfy_collect_gui_dict()
        return {
            "DIY_BAS_NTFY_ALLOWED": "true" if g["ntfy_allowed"] else "false",
            "DIY_BAS_NTFY_URL": str(g["ntfy_url"] or "").strip().rstrip("/") or "https://ntfy.sh",
            "DIY_BAS_NTFY_TOPIC": str(g["ntfy_topic"] or "").strip(),
            "DIY_BAS_NTFY_USERNAME": str(g["ntfy_username"] or "").strip(),
            "DIY_BAS_NTFY_PASSWORD": str(g["ntfy_password"] or ""),
            "DIY_BAS_NTFY_TIMEOUT_SEC": "20",
        }

    def _merge_ntfy_into_env_tab(self) -> None:
        body = self.txt_env.get("1.0", END)
        merged = merge_env_lines(body, self._ntfy_env_updates_from_gui())
        self.txt_env.delete("1.0", END)
        self.txt_env.insert("1.0", merged if merged.strip() else merged)

    def _on_ntfy_test_click(self) -> None:
        g = self._ntfy_collect_gui_dict()
        params = {
            "base_url": str(g["ntfy_url"] or "").strip() or "https://ntfy.sh",
            "topic": str(g["ntfy_topic"] or "").strip(),
            "title": str(g["ntfy_test_title"] or "BAS Alarm").strip(),
            "priority": str(g["ntfy_test_priority"] or "high"),
            "tags": str(g["ntfy_test_tags"] or "").strip(),
            "message": str(g["ntfy_test_message"] or "").strip() or " ",
            "username": str(g["ntfy_username"] or "").strip(),
            "password": str(g["ntfy_password"] or ""),
            "timeout_sec": 20,
        }
        if not params["topic"]:
            messagebox.showerror("ntfy", "Topic is required for a test send.")
            return

        def worker() -> None:
            try:
                snippet = _ntfy_send_raw(**params)
                self.root.after(0, lambda s=snippet: messagebox.showinfo("ntfy", f"Sent OK.\n\nResponse:\n{s[:800]}"))
            except Exception as e:
                self.root.after(0, lambda err=str(e): messagebox.showerror("ntfy failed", err))

        threading.Thread(target=worker, daemon=True).start()

    def _collect_deploy_cfg(self) -> dict:
        return {
            "pi_host": self.var_pi_host.get(),
            "pi_user": self.var_pi_user.get(),
            "ssh_password": self.var_ssh_pass.get(),
            "remote_dir": self.var_remote_dir.get(),
            "remote_bacnet_dir": self.var_remote_bacnet.get(),
            "run_bootstrap": self.v_run_bootstrap.get(),
            "start_app": self.v_start_app.get(),
            "use_docker_stack": self.v_docker_stack.get(),
            "test_login": self.v_test_login.get(),
            "sync_bootstrap_credentials": self.v_sync_bootstrap.get(),
            "docker_maintenance": self.v_docker_maint.get(),
            "verbose_deploy": self.v_verbose.get(),
            "login_username": self.var_login_user.get(),
            "login_password": self.var_login_pass.get(),
            "maint_username": self.var_maint_user.get(),
            "maint_password": self.var_maint_pass.get(),
            "bootstrap_log_tail": int(self.var_boot_tail.get() or 80),
            "compose_log_tail": int(self.var_compose_tail.get() or 50),
        }

    def _collect_full_state(self) -> dict:
        out = self._collect_deploy_cfg()
        try:
            fs = int(self.var_font_pt.get())
        except (ValueError, TypeError, self.tk.TclError):
            fs = _DEFAULT_TEXT_SIZE_PT
        out["ui_font_size"] = max(10, min(24, fs))
        out["show_advanced_deploy"] = bool(self.v_show_advanced.get())
        out.update(self._ntfy_collect_gui_dict())
        return out

    def _silent_save_state(self) -> None:
        try:
            STATE_PATH.write_text(json.dumps(self._collect_full_state(), indent=2), encoding="utf-8")
        except OSError:
            pass

    def _apply_deploy_cfg(self, d: dict) -> None:
        d = dict(d)
        for legacy in list(d.keys()):
            if legacy.startswith("smtp_"):
                d.pop(legacy, None)
        if "ntfy_enabled" in d and "ntfy_allowed" not in d:
            d["ntfy_allowed"] = d.get("ntfy_enabled")
        d.pop("ntfy_enabled", None)
        ntfy_saved = {k: d.pop(k) for k in _NTFY_STATE_KEYS if k in d}
        try:
            ui_font = int(d.pop("ui_font_size", _DEFAULT_TEXT_SIZE_PT))
        except (TypeError, ValueError):
            ui_font = _DEFAULT_TEXT_SIZE_PT
        ui_font = max(10, min(24, ui_font))
        show_adv = bool(d.pop("show_advanced_deploy", False))

        def set_entry(w, v: str) -> None:
            w.delete(0, END)
            w.insert(0, v)

        set_entry(self.var_pi_host, str(d.get("pi_host", "")))
        set_entry(self.var_pi_user, str(d.get("pi_user", "")))
        set_entry(self.var_ssh_pass, str(d.get("ssh_password", "")))
        set_entry(self.var_remote_dir, str(d.get("remote_dir", "")))
        set_entry(self.var_remote_bacnet, str(d.get("remote_bacnet_dir", "")))
        self.v_run_bootstrap.set(bool(d.get("run_bootstrap", True)))
        self.v_start_app.set(bool(d.get("start_app", True)))
        self.v_docker_stack.set(bool(d.get("use_docker_stack", True)))
        self.v_test_login.set(bool(d.get("test_login", True)))
        self.v_sync_bootstrap.set(bool(d.get("sync_bootstrap_credentials", True)))
        self.v_docker_maint.set(bool(d.get("docker_maintenance", True)))
        self.v_verbose.set(bool(d.get("verbose_deploy", False)))
        set_entry(self.var_login_user, str(d.get("login_username", "integrator")))
        set_entry(self.var_login_pass, str(d.get("login_password", "")))
        set_entry(self.var_maint_user, str(d.get("maint_username", "maintenance")))
        set_entry(self.var_maint_pass, str(d.get("maint_password", "")))
        self.var_boot_tail.delete(0, END)
        self.var_boot_tail.insert(0, str(d.get("bootstrap_log_tail", 80)))
        self.var_compose_tail.delete(0, END)
        self.var_compose_tail.insert(0, str(d.get("compose_log_tail", 50)))

        self.var_font_pt.set(int(ui_font))
        self.v_show_advanced.set(show_adv)
        self._apply_fonts()
        self._on_advanced_toggle()
        self._apply_ntfy_gui_state({**self._ntfy_default_state(), **ntfy_saved})

    def _load_state(self) -> None:
        defaults = {
            "pi_host": "192.168.204.12",
            "pi_user": "ben",
            "ssh_password": "",
            "remote_dir": "",
            "remote_bacnet_dir": "/home/ben/diy-bacnet-server",
            "run_bootstrap": True,
            "start_app": True,
            "use_docker_stack": True,
            "test_login": True,
            "sync_bootstrap_credentials": True,
            "docker_maintenance": True,
            "verbose_deploy": False,
            "login_username": "integrator",
            "login_password": "ChangeMeNow!123",
            "maint_username": "maintenance",
            "maint_password": "ChangeMeNow!123",
            "bootstrap_log_tail": 80,
            "compose_log_tail": 50,
            "ui_font_size": _DEFAULT_TEXT_SIZE_PT,
            "show_advanced_deploy": False,
        }
        defaults.update(self._ntfy_default_state())
        if STATE_PATH.is_file():
            try:
                saved = json.loads(STATE_PATH.read_text(encoding="utf-8"))
                if isinstance(saved, dict):
                    defaults.update({k: v for k, v in saved.items() if k in defaults})
                    if "ntfy_enabled" in saved and "ntfy_allowed" not in saved:
                        defaults["ntfy_allowed"] = saved["ntfy_enabled"]
            except (OSError, json.JSONDecodeError):
                pass
        self._apply_deploy_cfg(defaults)

    def _save_state(self) -> None:
        try:
            STATE_PATH.write_text(json.dumps(self._collect_full_state(), indent=2), encoding="utf-8")
            messagebox.showinfo("Saved", f"Settings saved to\n{STATE_PATH}")
        except OSError as e:
            messagebox.showerror("Save failed", str(e))

    def _on_close(self) -> None:
        self._silent_save_state()
        self.root.destroy()

    def _load_env_path(self, path: Path, *, silent: bool = False) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            if not silent:
                messagebox.showerror("Read failed", str(e))
            text = ""
        self.txt_env.delete("1.0", END)
        self.txt_env.insert("1.0", text)
        self._env_path = path

    def _load_env_file(self) -> None:
        self._load_env_path(ROOT / ".env")

    def _load_env_example(self) -> None:
        self._load_env_path(ROOT / ".env.example")

    def _save_env_file(self) -> None:
        path = getattr(self, "_env_path", ROOT / ".env")
        try:
            path.write_text(self.txt_env.get("1.0", END).rstrip("\n") + "\n", encoding="utf-8")
            messagebox.showinfo("Saved", str(path))
        except OSError as e:
            messagebox.showerror("Save failed", str(e))

    def _save_env_silent(self) -> bool:
        path = getattr(self, "_env_path", ROOT / ".env")
        try:
            path.write_text(self.txt_env.get("1.0", END).rstrip("\n") + "\n", encoding="utf-8")
            return True
        except OSError:
            return False

    def _open_env_other(self) -> None:
        p = filedialog.askopenfilename(initialdir=str(ROOT), filetypes=[("Env", "*.env"), ("All", "*")])
        if p:
            self._load_env_path(Path(p))

    def _fill_from_env_tab(self) -> None:
        env = parse_env_text(self.txt_env.get("1.0", END))
        if env.get("DIY_BACNET_SERVER_DIR"):
            self.var_remote_bacnet.delete(0, END)
            self.var_remote_bacnet.insert(0, env["DIY_BACNET_SERVER_DIR"])
        if env.get("DIY_BAS_ADMIN_USERNAME"):
            self.var_login_user.delete(0, END)
            self.var_login_user.insert(0, env["DIY_BAS_ADMIN_USERNAME"])
        if env.get("DIY_BAS_ADMIN_PASSWORD"):
            self.var_login_pass.delete(0, END)
            self.var_login_pass.insert(0, env["DIY_BAS_ADMIN_PASSWORD"])
        if env.get("DIY_BAS_MAINT_USERNAME"):
            self.var_maint_user.delete(0, END)
            self.var_maint_user.insert(0, env["DIY_BAS_MAINT_USERNAME"])
        if env.get("DIY_BAS_MAINT_PASSWORD"):
            self.var_maint_pass.delete(0, END)
            self.var_maint_pass.insert(0, env["DIY_BAS_MAINT_PASSWORD"])
        messagebox.showinfo(
            "Done",
            "If your .env had BACnet folder, admin, and maintenance lines, those are now in the top bar and deploy fields.",
        )

    def _push_logins_to_env_tab(self) -> None:
        updates = {
            "DIY_BAS_ADMIN_USERNAME": self.var_login_user.get().strip(),
            "DIY_BAS_ADMIN_PASSWORD": self.var_login_pass.get(),
            "DIY_BAS_MAINT_USERNAME": self.var_maint_user.get().strip(),
            "DIY_BAS_MAINT_PASSWORD": self.var_maint_pass.get(),
        }
        body = self.txt_env.get("1.0", END)
        merged = merge_env_lines(body, updates)
        self.txt_env.delete("1.0", END)
        self.txt_env.insert("1.0", merged if merged.strip() else merged)

    def _copy_cmd(self) -> None:
        cfg = self._collect_deploy_cfg()
        if sys.platform == "win32":
            argv = build_powershell_argv(cfg)
            line = subprocess.list2cmdline(argv)
        else:
            argv = build_python_ssh_argv(cfg)
            line = shlex.join(argv)

        self.root.clipboard_clear()
        self.root.clipboard_append(line)
        messagebox.showinfo("Clipboard", "Command copied.")

    def _copy_output(self) -> None:
        text = self.txt_log.get("1.0", END)
        if not text.strip():
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()

    def _check_ssh(self) -> None:
        host = self.var_pi_host.get().strip()
        user = self.var_pi_user.get().strip()
        if not host or not user:
            messagebox.showerror("SSH check", "Enter Pi address and Pi login name first.")
            return
        if self._proc is not None and self._proc.poll() is None:
            messagebox.showinfo("SSH check", "A deploy is still running. Wait for it to finish, then try again.")
            return
        if self._console_busy:
            messagebox.showinfo("SSH check", "The console is busy. Wait until you see --- finished --- below.")
            return

        target = f"{user}@{host}"
        ssh_password = self.var_ssh_pass.get()

        def worker() -> None:
            self.log_q.put(f"\n--- SSH check: {target} ---\n")
            pwd = (ssh_password or "").strip()
            if pwd:
                if sys.platform == "win32":
                    plink = shutil.which("plink")
                    if not plink:
                        self.log_q.put(
                            "\nSSH password was set, but `plink` (PuTTY) is not in PATH. "
                            "Install PuTTY and add its folder to PATH, or leave SSH password blank to use keys only.\n"
                        )
                        self._console_busy = False
                        self.log_q.put(None)
                        return
                    cmd = [plink, "-batch", "-ssh", "-pw", pwd, target, "echo", "DIY_BAS_SSH_OK"]
                else:
                    sshpass = shutil.which("sshpass")
                    if not sshpass:
                        self.log_q.put(
                            "\nSSH password was set, but `sshpass` is not installed. "
                            "Install it (e.g. brew install sshpass / apt install sshpass) or leave SSH password blank for keys.\n"
                        )
                        self._console_busy = False
                        self.log_q.put(None)
                        return
                    cmd = [
                        sshpass,
                        "-p",
                        pwd,
                        "ssh",
                        "-T",
                        "-o",
                        "ConnectTimeout=15",
                        "-o",
                        "StrictHostKeyChecking=accept-new",
                        target,
                        "echo DIY_BAS_SSH_OK",
                    ]
            else:
                cmd = [
                    "ssh",
                    "-T",
                    "-o",
                    "ConnectTimeout=15",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                    target,
                    "echo DIY_BAS_SSH_OK",
                ]
            try:
                p = subprocess.Popen(
                    cmd,
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                )
                assert p.stdout
                for line in p.stdout:
                    self.log_q.put(line)
                p.wait()
                if p.returncode == 0:
                    if pwd:
                        self.log_q.put("\nSSH check: OK (password auth).\n")
                    else:
                        self.log_q.put("\nSSH check: OK (key-based auth).\n")
                else:
                    self.log_q.put(
                        f"\nSSH check: could not connect (exit {p.returncode}). "
                        f"Try in a terminal: ssh {target}\n"
                    )
            except FileNotFoundError:
                self.log_q.put("\nSSH check: the 'ssh' program was not found. Install OpenSSH or use Git Bash.\n")
            except Exception as e:
                self.log_q.put(f"\nSSH check error: {e}\n")
            finally:
                self._console_busy = False
                self.log_q.put(None)

        self._console_busy = True
        self.txt_log.delete("1.0", END)
        threading.Thread(target=worker, daemon=True).start()

    def _append_log(self, s: str) -> None:
        self.txt_log.insert(END, s)
        self.txt_log.see(END)

    def _drain_log_queue(self) -> None:
        try:
            while True:
                item = self.log_q.get_nowait()
                if item is None:
                    self._append_log("\n--- finished ---\n")
                    break
                self._append_log(item)
        except queue.Empty:
            pass
        self.root.after(200, self._drain_log_queue)

    def _run_deploy(self) -> None:
        cfg = self._collect_deploy_cfg()
        if not cfg["pi_host"].strip() or not cfg["pi_user"].strip():
            messagebox.showerror("Deploy", "Pi address and Pi login name are required.")
            return
        if self._proc is not None and self._proc.poll() is None:
            messagebox.showinfo("Deploy", "A deploy is already running.")
            return
        if self._console_busy:
            messagebox.showinfo("Deploy", "The console is busy. Wait until you see --- finished --- below.")
            return

        # Same as "Write these logins into .env tab", then persist the current env buffer so disk
        # matches what you are deploying from (Integrator / Building Operator from the top bar).
        self._push_logins_to_env_tab()
        ntfy_push = bool(self.v_ntfy_allowed.get())
        if ntfy_push:
            self._merge_ntfy_into_env_tab()
        self._save_env_silent()

        self._silent_save_state()
        cfg = self._collect_deploy_cfg()
        cfg["ntfy_push"] = ntfy_push
        cfg["ntfy_env_for_pi"] = self._ntfy_env_updates_from_gui() if ntfy_push else {}

        def worker() -> None:
            try:
                if sys.platform == "win32":
                    ps1 = (ROOT / "deploy_to_pi.ps1").resolve()
                    self.log_q.put(f"Using repo script (same as .\\deploy_to_pi.ps1 from diy-bas): {ps1}\n\n")
                    argv = build_powershell_argv(cfg)
                    cmd_line = subprocess.list2cmdline(argv) + "\n\n"
                else:
                    argv = build_python_ssh_argv(cfg)
                    cmd_line = shlex.join(argv) + "\n\n"
                self.log_q.put(cmd_line)
                self._proc = subprocess.Popen(
                    argv,
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                )
                assert self._proc.stdout
                for line in self._proc.stdout:
                    self.log_q.put(line)
                self._proc.wait()
                if self._proc.returncode != 0:
                    self.log_q.put(f"\n[exit code {self._proc.returncode}]\n")
            except Exception as e:
                self.log_q.put(f"\nError: {e}\n")
            finally:
                self._proc = None
                self._console_busy = False
                self.log_q.put(None)

        self._console_busy = True
        self.txt_log.delete("1.0", END)
        threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    os.chdir(ROOT)
    app = DeployGuiApp()
    app.root.mainloop()


if __name__ == "__main__":
    main()
