from __future__ import annotations

import threading
from pathlib import Path

import click

from ..backup import backup_repeated
from ..config import ConfigError, MountConfig, load_config, load_mounts_config, resolve_config_path


def _normalize_path(path: Path) -> Path:
    return path.expanduser().resolve()


@click.command(name="backup-repeated")
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
def backup_repeated_command(source_dir: Path, dest_dir: Path, excludes: tuple[str, ...], interval: int) -> None:
    """Запускает циклическое резервное копирование каталога."""

    try:
        backup_repeated(
            _normalize_path(source_dir),
            _normalize_path(dest_dir),
            interval_minutes=interval,
            extra_excludes=list(excludes),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))


def _load_mounts(config_path: str | None) -> list[MountConfig]:
    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    config = load_config(resolved_path)
    return load_mounts_config(config)


def _find_mount_by_source(mounts, source: Path):
    normalized = _normalize_path(source)
    for mount in mounts:
        if mount.source == normalized:
            return mount
    return None


@click.command(name="backup-repeated-mount")
@click.option("--mount", "mount_path", required=True, type=click.Path(file_okay=False, path_type=Path), help="Путь к монтируемой папке из config.yaml")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию config.yaml или $CONFIG_PATH).",
)
def backup_repeated_mount_command(mount_path: Path, config_path: str | None) -> None:
    """Запускает циклический бэкап для монтирования из конфига."""

    try:
        mounts = _load_mounts(config_path)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    mount_entry = _find_mount_by_source(mounts, mount_path)
    if mount_entry is None:
        raise click.ClickException(f"Монтирование с путем {mount_path} не найдено в конфигурации")

    backup_repeated(mount_entry.source, mount_entry.backup, interval_minutes=mount_entry.interval_minutes)


@click.command(name="backup-repeated-all")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию config.yaml или $CONFIG_PATH).",
)
def backup_repeated_all_command(config_path: str | None) -> None:
    """Запускает циклические бэкапы для всех монтирований из config.yaml."""

    try:
        mounts = _load_mounts(config_path)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if not mounts:
        raise click.ClickException("В конфигурации нет монтирований для бэкапа")

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

    click.echo(f"Запущено {len(threads)} циклических бэкапов. Нажмите Ctrl+C для остановки.")

    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        click.echo("Остановка циклических бэкапов по запросу пользователя.")
