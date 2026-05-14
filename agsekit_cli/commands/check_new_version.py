from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from ..config import resolve_config_path
from ..i18n import tr
from ..state import CHANGELOG_URL, get_state_manager, initialize_state, run_check_new_version
from ..versioning import is_newer_version
from . import debug_option, non_interactive_option


@click.command(name="check-new-version", help=tr("check_new_version.command_help"))
@non_interactive_option
@debug_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def check_new_version_command(config_path: Optional[str], non_interactive: bool, debug: bool) -> None:
    """Check PyPI through pip, update state.yaml, and report whether a newer version exists."""
    del non_interactive
    del debug

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    initialize_state(resolved_path)
    manager = get_state_manager()
    try:
        latest = run_check_new_version()
    except RuntimeError as exc:
        raise click.ClickException(tr("check_new_version.failed", error=str(exc)))

    if is_newer_version(latest, manager.current_version):
        click.echo(
            tr(
                "check_new_version.newer_available",
                current=manager.current_version,
                latest=latest,
                changelog_url=CHANGELOG_URL,
            )
        )
        return

    click.echo(tr("check_new_version.already_latest", version=manager.current_version))
