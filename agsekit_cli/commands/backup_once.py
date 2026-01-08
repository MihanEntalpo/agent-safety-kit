from __future__ import annotations

from pathlib import Path

import click

from ..backup import backup_once
from ..i18n import tr
from . import non_interactive_option


@click.command(name="backup-once", help=tr("backup_once.command_help"))
@non_interactive_option
@click.option("--source-dir", required=True, type=click.Path(file_okay=False, path_type=Path), help=tr("backup_once.option_source_dir"))
@click.option("--dest-dir", required=True, type=click.Path(file_okay=False, path_type=Path), help=tr("backup_once.option_dest_dir"))
@click.option(
    "--exclude",
    "excludes",
    multiple=True,
    help=tr("backup_once.option_exclude"),
)
@click.option("--progress", "show_progress", is_flag=True, help=tr("backup_once.option_progress"))
def backup_once_command(
    source_dir: Path, dest_dir: Path, excludes: tuple[str, ...], show_progress: bool, non_interactive: bool
) -> None:
    """Run a single backup of a directory."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    click.echo(tr("backup_once.running", source=source_dir, destination=dest_dir))
    backup_once(source_dir, dest_dir, extra_excludes=list(excludes), show_progress=show_progress)
