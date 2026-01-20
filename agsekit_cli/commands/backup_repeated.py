from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import click

from . import non_interactive_option

from ..backup import backup_repeated
from ..config import ConfigError
from ..mounts import find_mount_by_source, load_mounts_from_config, normalize_path
from ..i18n import tr


@click.command(name="backup-repeated", help=tr("backup_repeated.command_help"))
@non_interactive_option
@click.option("--source-dir", required=True, type=click.Path(file_okay=False, path_type=Path), help=tr("backup_repeated.option_source_dir"))
@click.option("--dest-dir", required=True, type=click.Path(file_okay=False, path_type=Path), help=tr("backup_repeated.option_dest_dir"))
@click.option(
    "--exclude",
    "excludes",
    multiple=True,
    help=tr("backup_repeated.option_exclude"),
)
@click.option(
    "--interval",
    default=5,
    show_default=True,
    type=int,
    help=tr("backup_repeated.option_interval"),
)
@click.option(
    "--max-backups",
    default=100,
    show_default=True,
    type=int,
    help=tr("backup_repeated.option_max_backups"),
)
@click.option(
    "--backup-clean-method",
    default="thin",
    show_default=True,
    type=click.Choice(["tail", "thin"], case_sensitive=False),
    help=tr("backup_repeated.option_backup_clean_method"),
)
@click.option("--skip-first", is_flag=True, help=tr("backup_repeated.option_skip_first"))
def backup_repeated_command(
    source_dir: Path,
    dest_dir: Path,
    excludes: tuple[str, ...],
    interval: int,
    max_backups: int,
    backup_clean_method: str,
    skip_first: bool,
    non_interactive: bool,
) -> None:
    """Start repeated backups of a directory."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    click.echo(
        tr(
            "backup_repeated.starting",
            source=source_dir,
            destination=dest_dir,
            interval=interval,
        )
    )

    try:
        backup_repeated(
            normalize_path(source_dir),
            normalize_path(dest_dir),
            interval_minutes=interval,
            max_backups=max_backups,
            backup_clean_method=backup_clean_method,
            extra_excludes=list(excludes),
            skip_first=skip_first,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))


@click.command(name="backup-repeated-mount", help=tr("backup_repeated.mount_command_help"))
@non_interactive_option
@click.option("--mount", "mount_path", required=False, type=click.Path(file_okay=False, path_type=Path), help=tr("backup_repeated.option_mount"))
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def backup_repeated_mount_command(mount_path: Optional[Path], config_path: Optional[str], non_interactive: bool) -> None:
    """Start a repeated backup for a mount from the config."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    try:
        mounts = load_mounts_from_config(config_path)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    mount_entry = None
    if mount_path:
        mount_entry = find_mount_by_source(mounts, mount_path)
        if mount_entry is None:
            raise click.ClickException(tr("backup_repeated.mount_missing", source=mount_path))
    else:
        if not mounts:
            raise click.ClickException(tr("backup_repeated.no_mounts"))
        if len(mounts) == 1:
            mount_entry = mounts[0]
        else:
            raise click.ClickException(tr("backup_repeated.mount_required_multiple"))

    click.echo(
        tr(
            "backup_repeated.starting_mount",
            source=mount_entry.source,
            destination=mount_entry.backup,
            interval=mount_entry.interval_minutes,
        )
    )
    backup_repeated(
        mount_entry.source,
        mount_entry.backup,
        interval_minutes=mount_entry.interval_minutes,
        max_backups=mount_entry.max_backups,
        backup_clean_method=mount_entry.backup_clean_method,
    )


@click.command(name="backup-repeated-all", help=tr("backup_repeated.all_command_help"))
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def backup_repeated_all_command(config_path: Optional[str], non_interactive: bool) -> None:
    """Start repeated backups for every mount from config.yaml."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    try:
        mounts = load_mounts_from_config(config_path)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if not mounts:
        raise click.ClickException(tr("backup_repeated.no_mounts"))

    threads = []
    for mount in mounts:
        thread = threading.Thread(
            target=backup_repeated,
            args=(mount.source, mount.backup),
            kwargs={
                "interval_minutes": mount.interval_minutes,
                "max_backups": mount.max_backups,
                "backup_clean_method": mount.backup_clean_method,
            },
            daemon=True,
        )
        thread.start()
        threads.append(thread)

    click.echo(tr("backup_repeated.jobs_started", count=len(threads)))

    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        click.echo(tr("backup_repeated.stop_requested"))
