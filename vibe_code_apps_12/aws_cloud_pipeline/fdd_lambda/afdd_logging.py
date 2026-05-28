"""
Structured lines for CloudWatch (print) and dashboard server_log (JSON).
"""

from __future__ import annotations

import traceback
from typing import Any


class AfddLog:
    """Collect log lines for one request or go-live run."""

    __slots__ = ("_lines", "prefix")

    def __init__(self, prefix: str = "vibe12") -> None:
        self.prefix = prefix
        self._lines: list[str] = []

    def info(self, msg: str) -> str:
        return self._emit("INFO", msg)

    def warn(self, msg: str) -> str:
        return self._emit("WARN", msg)

    def error(self, msg: str, exc: BaseException | None = None) -> str:
        line = self._emit("ERROR", msg)
        if exc is not None:
            self._emit("ERROR", f"{type(exc).__name__}: {exc}")
            for tb_line in traceback.format_exc().strip().splitlines()[-4:]:
                self._emit("TRACE", tb_line)
        return line

    def _emit(self, level: str, msg: str) -> str:
        line = f"[{self.prefix}] {level} {msg}"
        print(line)
        self._lines.append(msg if level == "INFO" else f"{level}: {msg}")
        return line

    def extend(self, lines: list[str]) -> None:
        for ln in lines:
            if ln:
                self._lines.append(ln)

    def snapshot(self, limit: int = 40) -> list[str]:
        return self._lines[-limit:]


def debug_payload(log: AfddLog, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"server_log": log.snapshot()}
    out.update(extra)
    return out
