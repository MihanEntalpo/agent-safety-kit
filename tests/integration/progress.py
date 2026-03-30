from __future__ import annotations

import os
import sys
from typing import Any, Optional


AGSEKIT_IT_PROGRESS_ENV_VAR = "AGSEKIT_IT_PROGRESS"
_TERMINAL_REPORTER: Optional[Any] = None


def integration_progress_enabled() -> bool:
    value = os.environ.get(AGSEKIT_IT_PROGRESS_ENV_VAR, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def set_terminal_reporter(reporter: Any) -> None:
    global _TERMINAL_REPORTER
    _TERMINAL_REPORTER = reporter


def progress_line(message: str) -> None:
    if not integration_progress_enabled():
        return
    if _TERMINAL_REPORTER is not None:
        ensure_newline = getattr(_TERMINAL_REPORTER, "ensure_newline", None)
        if callable(ensure_newline):
            ensure_newline()
        _TERMINAL_REPORTER.write_line(message)
        return
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()
