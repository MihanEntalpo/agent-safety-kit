from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

import click
import questionary

Validator = Callable[[str], object]

NO_RESTRICTIONS_VALUE = "__no_restrictions__"
"""Sentinel checkbox value meaning that no allowlist restrictions should be stored."""

DEFAULT_BACKUPIGNORE_LINES = [
    "venv/",
    ".venv/",
    "__pycache__/",
    "*.pyc",
    "node_modules/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".tox/",
]
"""Reasonable default ignore patterns for source-tree backups."""


def ask_text(message: str, *, default: str = "", validate: Any = None) -> str:
    """Ask the user for one line of text and return the trimmed result.

    This wraps `questionary.text()` so command wizards can share one consistent
    text-input primitive with the same cancellation behavior.
    """

    value = questionary.text(message, default=default, validate=validate).ask()
    if value is None:
        raise click.Abort()
    return str(value).strip()


def ask_path(message: str, *, default: str = "", validate: Any = None) -> str:
    """Ask for a path-like string using the same behavior as a plain text prompt."""

    return ask_text(message, default=default, validate=validate)


def ask_confirm(message: str, *, default: bool) -> bool:
    """Ask a yes/no question and return the answer as a boolean."""

    value = questionary.confirm(message, default=default).ask()
    if value is None:
        raise click.Abort()
    return bool(value)


def ask_choice(
    message: str,
    *,
    choices: Sequence[str],
    default: Optional[str] = None,
    case_sensitive: bool = False,
) -> str:
    """Ask the user to choose one value from a fixed list.

    This uses `click.prompt(..., Choice(...))` instead of `questionary.select()`
    because it behaves more reliably in our PTY-based end-to-end tests.
    """

    return str(
        click.prompt(
            message,
            default=default or choices[0],
            type=click.Choice(list(choices), case_sensitive=case_sensitive),
        )
    ).strip()


def ask_select(
    message: str,
    *,
    choices: List[object],
    instruction: Optional[str] = None,
) -> object:
    """Ask the user to choose one item from a navigable TUI list."""

    kwargs: Dict[str, object] = {"choices": choices}
    if instruction is not None:
        kwargs["instruction"] = instruction
    value = questionary.select(message, **kwargs).ask()
    if value is None:
        raise click.Abort()
    return value


def ask_checkbox(
    message: str,
    *,
    choices: List[object],
    validate: Any = None,
    instruction: Optional[str] = None,
) -> List[object]:
    """Ask the user to choose zero or more items from a checkbox list."""

    kwargs: Dict[str, object] = {"choices": choices}
    if validate is not None:
        kwargs["validate"] = validate
    if instruction is not None:
        kwargs["instruction"] = instruction
    value = questionary.checkbox(message, **kwargs).ask()
    if value is None:
        raise click.Abort()
    return list(value)


def make_required_validator(error_message: str) -> Validator:
    """Build a validator that accepts only non-empty trimmed input."""

    def _validate(value: str) -> object:
        if str(value).strip():
            return True
        return error_message

    return _validate


def make_positive_int_validator(required_message: str, positive_message: str) -> Validator:
    """Build a validator that accepts only positive integers."""

    def _validate(value: str) -> object:
        text = str(value).strip()
        if not text:
            return required_message
        try:
            parsed = int(text)
        except ValueError:
            return positive_message
        if parsed <= 0:
            return positive_message
        return True

    return _validate


def parse_positive_int(value: str) -> int:
    """Parse a string that has already been validated as a positive integer."""

    return int(value.strip())


def require_non_empty_selection(values: List[object], error_message: str) -> object:
    """Validate that a checkbox or multiselect answer contains at least one item."""

    if values:
        return True
    return error_message
