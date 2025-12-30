from __future__ import annotations

import threading
from pathlib import Path

import click

from . import non_interactive_option

from ..backup import backup_repeated
from ..config import ConfigError
from ..mounts import find_mount_by_source, load_mounts_from_config, normalize_path


@click.command(name="backup-repeated")
@non_interactive_option
@click.option("--source-dir", required=True, type=click.Path(file_okay=False, path_type=Path), help="Директория для бэкапа")
@click.option("--dest-dir", required=True, type=click.Path(file_okay=False, path_type=Path), help="Куда складывать снапшоты")
@click.option(
    "--exclude",
    "excludes",
    multiple=True,
    help="Дополнительный паттерн исключений rsync; можно указать несколько раз",
)
@click.option(
    "--interval",
    default=5,
    show_default=True,
    type=int,
    help="Интервал в минутах между бэкапами",
)
def backup_repeated_command(
    source_dir: Path, dest_dir: Path, excludes: tuple[str, ...], interval: int, non_interactive: bool
) -> None:
    """Start repeated backups of a directory."""

    click.echo(
        f"Starting repeated backup from {source_dir} to {dest_dir} every {interval} minute(s)..."
    )

    try:
        backup_repeated(
            normalize_path(source_dir),
            normalize_path(dest_dir),
            interval_minutes=interval,
            extra_excludes=list(excludes),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))


@click.command(name="backup-repeated-mount")
@non_interactive_option
@click.option("--mount", "mount_path", required=False, type=click.Path(file_okay=False, path_type=Path), help="Путь к монтируемой папке из config.yaml")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию ~/.config/agsekit/config.yaml или $CONFIG_PATH).",
)
def backup_repeated_mount_command(mount_path: Path, config_path: str | None, non_interactive: bool) -> None:
    """Start a repeated backup for a mount from the config."""

    try:
        mounts = load_mounts_from_config(config_path)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    mount_entry = None
    if mount_path:
        mount_entry = find_mount_by_source(mounts, mount_path)
        if mount_entry is None:
            raise click.ClickException(f"Mount with source {mount_path} is not defined in the configuration.")
    else:
        if not mounts:
            raise click.ClickException("No mounts configured for backups.")
        if len(mounts) == 1:
            mount_entry = mounts[0]
        else:
            raise click.ClickException("Несколько монтирований в конфигурации. Укажите путь через --mount.")

    click.echo(
        f"Starting repeated backup for mount {mount_entry.source} -> {mount_entry.backup} every {mount_entry.interval_minutes} minute(s)..."
    )
    backup_repeated(mount_entry.source, mount_entry.backup, interval_minutes=mount_entry.interval_minutes)


@click.command(name="backup-repeated-all")
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию ~/.config/agsekit/config.yaml или $CONFIG_PATH).",
)
def backup_repeated_all_command(config_path: str | None, non_interactive: bool) -> None:
    """Start repeated backups for every mount from config.yaml."""

    try:
        mounts = load_mounts_from_config(config_path)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if not mounts:
        raise click.ClickException("No mounts configured for backups.")

    threads = []
    for mount in mounts:
        thread = threading.Thread(
            target=backup_repeated,
            args=(mount.source, mount.backup),
            kwargs={"interval_minutes": mount.interval_minutes},
            daemon=True,
        )
        thread.start()
        threads.append(thread)

    click.echo(
        f"Started {len(threads)} repeated backup job(s). Press Ctrl+C to stop when you're done."
    )

    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        click.echo("Stopping repeated backups on user request.")
