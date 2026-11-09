from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

import click
import questionary

from ..config import resolve_config_path
from ..i18n import tr
from ..interactive import is_interactive_terminal
from . import non_interactive_option


FALLBACK_EDITORS = ("vim", "vi", "nano", "pico")


def _editor_from_environment() -> Optional[List[str]]:
    value = os.environ.get("EDITOR", "").strip()
    if not value:
        return None
    try:
        command = shlex.split(value)
    except ValueError as exc:
        raise click.ClickException(tr("config_edit.editor_invalid", editor=value, error=exc)) from exc
    if not command:
        return None
    if shutil.which(command[0]) is None:
        raise click.ClickException(tr("config_edit.editor_not_found", editor=command[0]))
    return command


def _select_fallback_editor() -> Optional[str]:
    available = [editor for editor in FALLBACK_EDITORS if shutil.which(editor) is not None]
    if not available:
        return None
    selected = questionary.select(
        tr("config_edit.editor_select"),
        choices=[questionary.Choice(editor, value=editor) for editor in available],
        use_shortcuts=True,
    ).ask()
    if selected is None:
        raise click.Abort()
    return str(selected)


@click.command(name="edit", help=tr("config_edit.command_help"))
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=Path),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def config_edit_command(config_path: Optional[Path], non_interactive: bool) -> None:
    """Open the resolved host-side configuration file in a text editor."""

    command = _editor_from_environment()
    if command is None:
        if non_interactive or not is_interactive_terminal():
            raise click.ClickException(tr("config_edit.editor_required"))
        selected = _select_fallback_editor()
        if selected is None:
            raise click.ClickException(tr("config_edit.editor_required"))
        command = [selected]

    target_path = resolve_config_path(config_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    click.echo(tr("config_edit.opening", path=target_path, editor=command[0]))
    try:
        result = subprocess.run([*command, str(target_path)], check=False)
    except OSError as exc:
        raise click.ClickException(tr("config_edit.editor_launch_failed", editor=command[0], error=exc)) from exc
    if result.returncode != 0:
        raise click.ClickException(tr("config_edit.editor_failed", editor=command[0], code=result.returncode))
