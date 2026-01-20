from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from . import non_interactive_option
from ..backup import clean_backups
from ..config import ConfigError
from ..i18n import tr
from ..mounts import find_mount_by_source, load_mounts_from_config


@click.command(name="backup-clean", help=tr("backup_clean.command_help"))
@non_interactive_option
@click.argument("mount_source", type=click.Path(file_okay=False, path_type=Path))
@click.argument("keep", required=False, default=50, type=int)
@click.argument(
    "method",
    required=False,
    default="tail",
    type=click.Choice(["tail", "thin"], case_sensitive=False),
)
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def backup_clean_command(
    mount_source: Path,
    keep: int,
    method: str,
    config_path: Optional[str],
    non_interactive: bool,
) -> None:
    """Clean old backup snapshots for a mount."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    if keep < 0:
        raise click.ClickException(tr("backup_clean.keep_non_negative"))

    try:
        mounts = load_mounts_from_config(config_path)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    mount_entry = find_mount_by_source(mounts, mount_source)
    if mount_entry is None:
        raise click.ClickException(tr("backup_clean.mount_missing", source=mount_source))

    backup_dir = mount_entry.backup
    if not backup_dir.exists():
        raise click.ClickException(tr("backup_clean.backup_missing", path=backup_dir))

    try:
        removed = clean_backups(
            backup_dir,
            keep,
            method,
            interval_minutes=mount_entry.interval_minutes,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))

    if not removed:
        click.echo(tr("backup_clean.nothing_removed", keep=keep))
        return

    for path in removed:
        click.echo(tr("backup_clean.removed_snapshot", path=path))
