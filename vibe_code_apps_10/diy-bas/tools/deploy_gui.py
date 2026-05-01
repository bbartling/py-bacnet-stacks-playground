#!/usr/bin/env python3
"""
Tkinter GUI: edit local .env, configure Pi deploy options, run deploy_to_pi.ps1 (Windows)
or tools/deploy_via_ssh.py (Linux/macOS).
"""
from __future__ import annotations

import json
import os
import queue
import shlex
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import BOTH, END, LEFT, NSEW, RIGHT, W, X, Y, scrolledtext, ttk, messagebox, filedialog

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
STATE_PATH = Path.home() / ".diy-bas-deploy-gui.json"


def _ps_bool(b: bool) -> str:
    return "$true" if b else "$false"


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
    rd = (cfg.get("remote_dir") or "").strip()
    if rd:
        args.extend(["-RemoteDir", rd])
    rbd = (cfg.get("remote_bacnet_dir") or "").strip()
    if rbd:
        args.extend(["-RemoteBacnetDir", rbd])
    args.append(f"-RunBootstrap:{_ps_bool(bool(cfg.get('run_bootstrap')))}")
    args.append(f"-StartApp:{_ps_bool(bool(cfg.get('start_app')))}")
    args.append(f"-UseDockerStack:{_ps_bool(bool(cfg.get('use_docker_stack')))}")
    args.append(f"-TestLogin:{_ps_bool(bool(cfg.get('test_login')))}")
    args.append(f"-SyncBootstrapCredentialsFromExample:{_ps_bool(bool(cfg.get('sync_bootstrap_credentials')))}")
    args.append(f"-DockerMaintenance:{_ps_bool(bool(cfg.get('docker_maintenance')))}")
    args.extend(["-LoginUsername", cfg.get("login_username") or "integrator"])
    args.extend(["-LoginPassword", cfg.get("login_password") or ""])
    args.append(f"-VerboseDeploy:{_ps_bool(bool(cfg.get('verbose_deploy')))}")
    args.extend(["-BootstrapLogTail", str(int(cfg.get("bootstrap_log_tail") or 80))])
    args.extend(["-ComposeLogTail", str(int(cfg.get("compose_log_tail") or 50))])
    return args


def build_python_ssh_argv(cfg: dict) -> list[str]:
    """Argv for: python tools/deploy_via_ssh.py ..."""
    script = TOOLS / "deploy_via_ssh.py"
    args: list[str] = [sys.executable, str(script), "--pi-host", cfg["pi_host"].strip(), "--pi-user", cfg["pi_user"].strip()]
    rd = (cfg.get("remote_dir") or "").strip()
    if rd:
        args.extend(["--remote-dir", rd])
    rbd = (cfg.get("remote_bacnet_dir") or "").strip()
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
    args.extend(["--login-username", cfg.get("login_username") or "integrator"])
    args.extend(["--login-password", cfg.get("login_password") or ""])
    if cfg.get("verbose_deploy"):
        args.append("--verbose-deploy")
    args.extend(["--bootstrap-log-tail", str(int(cfg.get("bootstrap_log_tail") or 80))])
    args.extend(["--compose-log-tail", str(int(cfg.get("compose_log_tail") or 50))])
    return args


class DeployGuiApp:
    def __init__(self) -> None:
        import tkinter as tk

        self.tk = tk
        self.root = tk.Tk()
        self.root.title("diy-bas — deploy to Pi")
        self.root.geometry("920x640")
        self.root.minsize(720, 480)

        self.log_q: queue.Queue[str | None] = queue.Queue()
        self._proc: subprocess.Popen[str] | None = None

        nb = ttk.Notebook(self.root)
        nb.pack(fill=BOTH, expand=True, padx=8, pady=8)

        self.tab_deploy = ttk.Frame(nb, padding=6)
        self.tab_env = ttk.Frame(nb, padding=6)
        nb.add(self.tab_deploy, text="Deploy to Pi")
        nb.add(self.tab_env, text=".env editor")

        self._build_deploy_tab()
        self._build_env_tab()
        self._load_state()
        self.root.after(200, self._drain_log_queue)

    def _build_deploy_tab(self) -> None:
        f = self.tab_deploy
        row = 0

        def add_row(label: str, widget) -> None:
            nonlocal row
            ttk.Label(f, text=label).grid(row=row, column=0, sticky=W, pady=2, padx=(0, 8))
            widget.grid(row=row, column=1, sticky=W + X, pady=2)
            f.columnconfigure(1, weight=1)
            row += 1

        self.var_pi_host = ttk.Entry(f, width=48)
        self.var_pi_user = ttk.Entry(f, width=24)
        self.var_remote_dir = ttk.Entry(f, width=48)
        self.var_remote_bacnet = ttk.Entry(f, width=48)
        add_row("Pi host (IP or DNS)", self.var_pi_host)
        add_row("Pi SSH user", self.var_pi_user)
        add_row("Remote app dir (blank = /home/<user>/diy-bas)", self.var_remote_dir)
        add_row("Remote BACnet dir (blank = /home/<user>/diy-bacnet-server)", self.var_remote_bacnet)

        opts = ttk.LabelFrame(f, text="Options", padding=6)
        opts.grid(row=row, column=0, columnspan=2, sticky=W + X, pady=8)
        row += 1

        tk = self.tk
        self.v_run_bootstrap = tk.BooleanVar(value=True)
        self.v_start_app = tk.BooleanVar(value=True)
        self.v_docker_stack = tk.BooleanVar(value=True)
        self.v_test_login = tk.BooleanVar(value=True)
        self.v_sync_bootstrap = tk.BooleanVar(value=True)
        self.v_docker_maint = tk.BooleanVar(value=True)
        self.v_verbose = tk.BooleanVar(value=False)
        self.chk_run_bootstrap = ttk.Checkbutton(
            opts, text="Run bootstrap (BOOTSTRAP_NO_RUN=1)", variable=self.v_run_bootstrap
        )
        self.chk_start_app = ttk.Checkbutton(opts, text="Start app (Docker compose)", variable=self.v_start_app)
        self.chk_docker_stack = ttk.Checkbutton(
            opts, text="Use Docker stack (Caddy + diy-bas)", variable=self.v_docker_stack
        )
        self.chk_test_login = ttk.Checkbutton(opts, text="Test login after deploy", variable=self.v_test_login)
        self.chk_sync_bootstrap = ttk.Checkbutton(
            opts, text="Sync bootstrap credentials from .env.example on Pi", variable=self.v_sync_bootstrap
        )
        self.chk_docker_maint = ttk.Checkbutton(
            opts, text="Docker maintenance (down old .bak, prune)", variable=self.v_docker_maint
        )
        self.chk_verbose = ttk.Checkbutton(
            opts, text="Verbose Docker build (--progress=plain)", variable=self.v_verbose
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

        cred = ttk.LabelFrame(f, text="Login verification (Pi curl)", padding=6)
        cred.grid(row=row, column=0, columnspan=2, sticky=W + X, pady=4)
        row += 1
        ttk.Label(cred, text="Username").grid(row=0, column=0, sticky=W)
        self.var_login_user = ttk.Entry(cred, width=28)
        self.var_login_user.grid(row=0, column=1, sticky=W, padx=6)
        ttk.Label(cred, text="Password").grid(row=1, column=0, sticky=W)
        self.var_login_pass = ttk.Entry(cred, width=36, show="*")
        self.var_login_pass.grid(row=1, column=1, sticky=W, padx=6)

        tail = ttk.Frame(f)
        tail.grid(row=row, column=0, columnspan=2, sticky=W, pady=4)
        row += 1
        ttk.Label(tail, text="Bootstrap log tail").pack(side=LEFT)
        self.var_boot_tail = ttk.Spinbox(tail, from_=10, to=500, width=8)
        self.var_boot_tail.pack(side=LEFT, padx=(6, 24))
        ttk.Label(tail, text="Compose log tail").pack(side=LEFT)
        self.var_compose_tail = ttk.Spinbox(tail, from_=10, to=500, width=8)
        self.var_compose_tail.pack(side=LEFT, padx=6)

        hint = (
            "Windows: runs deploy_to_pi.ps1 (needs robocopy). "
            "Linux/macOS: runs tools/deploy_via_ssh.py (needs ssh, scp, zip on Pi for unzip)."
        )
        ttk.Label(f, text=hint, wraplength=860).grid(row=row, column=0, columnspan=2, sticky=W, pady=6)
        row += 1

        btns = ttk.Frame(f)
        btns.grid(row=row, column=0, columnspan=2, sticky=W, pady=6)
        row += 1
        ttk.Button(btns, text="Run deploy", command=self._run_deploy).pack(side=LEFT, padx=(0, 8))
        ttk.Button(btns, text="Copy command to clipboard", command=self._copy_cmd).pack(side=LEFT, padx=(0, 8))
        ttk.Button(btns, text="Fill from .env tab", command=self._fill_from_env_tab).pack(side=LEFT, padx=(0, 8))
        ttk.Button(btns, text="Save settings", command=self._save_state).pack(side=LEFT)

        logf = ttk.LabelFrame(f, text="Output", padding=4)
        logf.grid(row=row, column=0, columnspan=2, sticky=NSEW, pady=8)
        f.rowconfigure(row, weight=1)
        f.columnconfigure(0, weight=1)
        self.txt_log = scrolledtext.ScrolledText(logf, height=14, wrap="word", font=("Consolas", 9) if sys.platform == "win32" else ("Menlo", 10))
        self.txt_log.pack(fill=BOTH, expand=True)

    def _build_env_tab(self) -> None:
        f = self.tab_env
        bar = ttk.Frame(f)
        bar.pack(fill=X, pady=(0, 6))
        ttk.Button(bar, text="Load .env", command=self._load_env_file).pack(side=LEFT, padx=(0, 6))
        ttk.Button(bar, text="Load .env.example", command=self._load_env_example).pack(side=LEFT, padx=(0, 6))
        ttk.Button(bar, text="Save .env", command=self._save_env_file).pack(side=LEFT, padx=(0, 6))
        ttk.Button(bar, text="Open other…", command=self._open_env_other).pack(side=LEFT, padx=(0, 6))
        ttk.Button(bar, text="Apply keys to Deploy tab", command=self._fill_from_env_tab).pack(side=LEFT)

        self.txt_env = scrolledtext.ScrolledText(f, wrap="none", font=("Consolas", 10) if sys.platform == "win32" else ("Menlo", 11))
        self.txt_env.pack(fill=BOTH, expand=True)
        self._env_path = ROOT / ".env"
        self._load_env_path(self._env_path, silent=True)

    def _collect_deploy_cfg(self) -> dict:
        return {
            "pi_host": self.var_pi_host.get(),
            "pi_user": self.var_pi_user.get(),
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
            "bootstrap_log_tail": int(self.var_boot_tail.get() or 80),
            "compose_log_tail": int(self.var_compose_tail.get() or 50),
        }

    def _apply_deploy_cfg(self, d: dict) -> None:
        def set_entry(w, v: str) -> None:
            w.delete(0, END)
            w.insert(0, v)

        set_entry(self.var_pi_host, str(d.get("pi_host", "")))
        set_entry(self.var_pi_user, str(d.get("pi_user", "")))
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
        self.var_boot_tail.delete(0, END)
        self.var_boot_tail.insert(0, str(d.get("bootstrap_log_tail", 80)))
        self.var_compose_tail.delete(0, END)
        self.var_compose_tail.insert(0, str(d.get("compose_log_tail", 50)))

    def _load_state(self) -> None:
        defaults = {
            "pi_host": "192.168.204.12",
            "pi_user": "ben",
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
            "bootstrap_log_tail": 80,
            "compose_log_tail": 50,
        }
        if STATE_PATH.is_file():
            try:
                saved = json.loads(STATE_PATH.read_text(encoding="utf-8"))
                if isinstance(saved, dict):
                    defaults.update({k: v for k, v in saved.items() if k in defaults})
            except (OSError, json.JSONDecodeError):
                pass
        self._apply_deploy_cfg(defaults)

    def _save_state(self) -> None:
        try:
            STATE_PATH.write_text(json.dumps(self._collect_deploy_cfg(), indent=2), encoding="utf-8")
            messagebox.showinfo("Saved", f"Deploy form saved to\n{STATE_PATH}")
        except OSError as e:
            messagebox.showerror("Save failed", str(e))

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
        messagebox.showinfo("Applied", "Updated remote BACnet dir and login fields from editor text (if keys were present).")

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
            messagebox.showerror("Deploy", "Pi host and Pi user are required.")
            return

        def worker() -> None:
            try:
                if sys.platform == "win32":
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
                self.log_q.put(None)

        self.txt_log.delete("1.0", END)
        threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    os.chdir(ROOT)
    app = DeployGuiApp()
    app.root.mainloop()


if __name__ == "__main__":
    main()
