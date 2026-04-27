from __future__ import annotations

import os
import shlex
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional, Sequence, Union

import click

from .i18n import tr

DEBUG_ENV_VAR = "AGSEKIT_DEBUG"
DEBUG_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def is_debug_enabled(explicit: Optional[bool] = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    return os.environ.get(DEBUG_ENV_VAR, "").lower() in {"1", "true", "yes", "on"}


@contextmanager
def debug_scope(enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return

    previous = os.environ.get(DEBUG_ENV_VAR)
    os.environ[DEBUG_ENV_VAR] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(DEBUG_ENV_VAR, None)
        else:
            os.environ[DEBUG_ENV_VAR] = previous


def _format_command(command: Union[Sequence[str], str]) -> str:
    if isinstance(command, str):
        return command
    return shlex.join([str(part) for part in command])


def _output_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _debug_timestamp() -> str:
    return datetime.now().strftime(DEBUG_TIMESTAMP_FORMAT)[:-3]


def _debug_echo(message_key: str, **kwargs: object) -> None:
    click.echo(tr(message_key, timestamp=_debug_timestamp(), **kwargs))


def debug_log_command(command: Union[Sequence[str], str], *, enabled: Optional[bool] = None) -> None:
    if not is_debug_enabled(enabled):
        return
    _debug_echo("debug.command", command=_format_command(command))


def debug_log_result(result: object, *, enabled: Optional[bool] = None) -> None:
    if not is_debug_enabled(enabled):
        return

    returncode = getattr(result, "returncode", None)
    _debug_echo("debug.exit_code", code=returncode)

    stdout = _output_text(getattr(result, "stdout", None)).strip()
    stderr = _output_text(getattr(result, "stderr", None)).strip()

    if stdout:
        _debug_echo("debug.stdout", output=stdout)
    if stderr:
        _debug_echo("debug.stderr", output=stderr)
