from __future__ import annotations

from pathlib import Path
from typing import List

import click

from ..config import ConfigError, MountConfig
from ..mounts import find_mount_by_source, load_mounts_from_config, mount_directory, normalize_path, umount_directory
from ..vm import MultipassError
from . import non_interactive_option


def _select_mounts(source_dir: Path | None, mount_all: bool, config_path: str | None) -> List[MountConfig]:
    if bool(source_dir) == mount_all:
        raise click.ClickException("Provide either --source-dir or --all, but not both.")

    try:
        mounts = load_mounts_from_config(config_path)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if mount_all:
        if not mounts:
            raise click.ClickException("No mounts found in the configuration.")
        return list(mounts)

    assert source_dir is not None
    mount_entry = find_mount_by_source(mounts, source_dir)
    if mount_entry is None:
        raise click.ClickException(f"Mount with source {source_dir} is not defined in the configuration.")
    return [mount_entry]


@click.command(name="mount")
@non_interactive_option
@click.option("--source-dir", type=click.Path(file_okay=False, path_type=Path), help="Путь к папке из config.yaml")
@click.option("--all", "mount_all", is_flag=True, help="Смонтировать все папки из config.yaml")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию ~/.config/agsekit/config.yaml или $CONFIG_PATH).",
)
def mount_command(source_dir: Path | None, mount_all: bool, config_path: str | None, non_interactive: bool) -> None:
    """Mount directories from config.yaml into VMs."""

    click.echo("Mounting requested directories via multipass...")

    mounts = _select_mounts(source_dir, mount_all, config_path)

    for mount in mounts:
        try:
            mount_directory(mount)
        except MultipassError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"Mounted {normalize_path(mount.source)} -> {mount.vm_name}:{mount.target}")


@click.command(name="umount")
@non_interactive_option
@click.option("--source-dir", type=click.Path(file_okay=False, path_type=Path), help="Путь к папке из config.yaml")
@click.option("--all", "mount_all", is_flag=True, help="Отмонтировать все папки из config.yaml")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию ~/.config/agsekit/config.yaml или $CONFIG_PATH).",
)
def umount_command(source_dir: Path | None, mount_all: bool, config_path: str | None, non_interactive: bool) -> None:
    """Unmount directories from config.yaml."""

    click.echo("Unmounting selected directories via multipass...")

    mounts = _select_mounts(source_dir, mount_all, config_path)

    for mount in mounts:
        try:
            umount_directory(mount)
        except MultipassError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"Unmounted {mount.vm_name}:{mount.target}")
