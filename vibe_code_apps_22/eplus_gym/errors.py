"""Typed EnergyPlus gym failures (preserve eplusout.err text)."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class EnergyPlusStartupError(RuntimeError):
    """EnergyPlus aborted before the gym received a first observation."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int | None = None,
        runner_error: str | None = None,
        err_path: Path | str | None = None,
        severe_or_fatal: str | None = None,
        log_tail: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.runner_error = runner_error
        self.err_path = Path(err_path) if err_path else None
        self.severe_or_fatal = severe_or_fatal
        self.log_tail = log_tail
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "EnergyPlusStartupError",
            "message": str(self),
            "exit_code": self.exit_code,
            "runner_error": self.runner_error,
            "err_path": str(self.err_path) if self.err_path else None,
            "severe_or_fatal": self.severe_or_fatal,
            "log_tail": self.log_tail,
            "details": self.details,
        }
