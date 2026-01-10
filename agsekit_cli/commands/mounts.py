from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import click

from ..config import ConfigError, MountConfig
from ..i18n import tr
from ..mounts import (
    MountAlreadyMountedError,
    find_mount_by_source,
    load_mounts_from_config,
    mount_directory,
    normalize_path,
    umount_directory,
)
from ..vm import MultipassError
from . import non_interactive_option


def _select_mounts(source_dir: Optional[Path], mount_all: bool, config_path: Optional[str]) -> List[MountConfig]:
    if source_dir and mount_all:
        raise click.ClickException(tr("mounts.command_conflict"))

    try:
        mounts = load_mounts_from_config(config_path)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if mount_all:
        if not mounts:
            raise click.ClickException(tr("mounts.none_configured"))
        return list(mounts)

    if source_dir is not None:
        mount_entry = find_mount_by_source(mounts, source_dir)
        if mount_entry is None:
            raise click.ClickException(tr("mounts.source_not_defined", source=source_dir))
        return [mount_entry]

    if not mounts:
        raise click.ClickException(tr("mounts.none_configured"))
    if len(mounts) == 1:
        return [mounts[0]]

    raise click.ClickException(tr("mounts.require_selector_multiple"))


@click.command(name="mount", help=tr("mounts.command_mount_help"))
@non_interactive_option
@click.option("--source-dir", type=click.Path(file_okay=False, path_type=Path), help=tr("mounts.option_source_dir"))
@click.option("--all", "mount_all", is_flag=True, help=tr("mounts.option_all_mounts"))
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def mount_command(source_dir: Optional[Path], mount_all: bool, config_path: Optional[str], non_interactive: bool) -> None:
    """Mount directories from config.yaml into VMs."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    click.echo(tr("mounts.mounting_requested"))

    mounts = _select_mounts(source_dir, mount_all, config_path)

    for mount in mounts:
        try:
            mount_directory(mount)
        except MountAlreadyMountedError:
            click.echo(
                tr(
                    "mounts.already_mounted",
                    source=normalize_path(mount.source),
                    vm_name=mount.vm_name,
                    target=mount.target,
                )
            )
            continue
        except MultipassError as exc:
            raise click.ClickException(str(exc))
        click.echo(
            tr(
                "mounts.mounted",
                source=normalize_path(mount.source),
                vm_name=mount.vm_name,
                target=mount.target,
            )
        )


@click.command(name="umount", help=tr("mounts.command_umount_help"))
@non_interactive_option
@click.option("--source-dir", type=click.Path(file_okay=False, path_type=Path), help=tr("mounts.option_source_dir"))
@click.option("--all", "mount_all", is_flag=True, help=tr("mounts.option_all_umounts"))
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def umount_command(source_dir: Optional[Path], mount_all: bool, config_path: Optional[str], non_interactive: bool) -> None:
    """Unmount directories from config.yaml."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    click.echo(tr("mounts.unmounting_requested"))

    mounts = _select_mounts(source_dir, mount_all, config_path)

    for mount in mounts:
        try:
            umount_directory(mount)
        except MultipassError as exc:
            raise click.ClickException(str(exc))
        click.echo(tr("mounts.unmounted", vm_name=mount.vm_name, target=mount.target))
