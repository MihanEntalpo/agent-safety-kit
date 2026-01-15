from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
from typing import Optional

import click
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from . import non_interactive_option
from ..config import ConfigError, MountConfig, load_mounts_config, resolve_config_path
from ..i18n import tr
from ..interactive import is_interactive_terminal
from ..mounts import normalize_path, umount_directory
from ..vm import MultipassError


def _load_config_with_comments(config_path: Path) -> tuple[YAML, CommentedMap]:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.load(handle)
    except YAMLError as exc:
        raise click.ClickException(tr("removemount.config_parse_failed", path=config_path, error=exc)) from exc

    if loaded is None:
        return yaml, CommentedMap()
    if not isinstance(loaded, dict):
        raise click.ClickException(tr("config.root_not_mapping"))
    if not isinstance(loaded, CommentedMap):
        loaded = CommentedMap(loaded)
    return yaml, loaded


def _backup_config(config_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = config_path.with_name(f"{config_path.stem}-backup-{timestamp}.yaml")
    shutil.copy2(config_path, backup_path)
    return backup_path


def _prompt_mount_choice(matches: list[tuple[int, MountConfig]]) -> tuple[int, MountConfig]:
    click.echo(tr("removemount.select_intro"))
    for index, (_, mount) in enumerate(matches, start=1):
        click.echo(
            tr(
                "removemount.select_item",
                index=index,
                source=mount.source,
                vm_name=mount.vm_name,
                target=mount.target,
            )
        )
    selection = click.prompt(tr("removemount.select_prompt"), type=click.IntRange(1, len(matches)))
    return matches[selection - 1]


def _select_mount(
    mounts: list[MountConfig],
    source_dir: Optional[Path],
    vm_name: Optional[str],
    interactive: bool,
) -> tuple[int, MountConfig]:
    if not mounts:
        raise click.ClickException(tr("removemount.none_configured"))

    matches = []
    if source_dir is not None:
        normalized = normalize_path(source_dir)
        matches = [(index, mount) for index, mount in enumerate(mounts) if mount.source == normalized]
        if vm_name:
            matches = [(index, mount) for index, mount in matches if mount.vm_name == vm_name]

        if not matches:
            suffix = tr("removemount.vm_suffix", vm_name=vm_name) if vm_name else ""
            raise click.ClickException(tr("removemount.mount_not_found", source=normalized, suffix=suffix))
        if len(matches) == 1:
            return matches[0]
        if not interactive:
            raise click.ClickException(tr("removemount.multiple_matches"))
        return _prompt_mount_choice(matches)

    if not interactive:
        raise click.ClickException(tr("removemount.source_required"))
    matches = list(enumerate(mounts))
    return _prompt_mount_choice(matches)


@click.command(name="removemount", help=tr("removemount.command_help"))
@non_interactive_option
@click.argument("source_dir", required=False, type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--vm",
    "vm_name",
    required=False,
    help=tr("removemount.option_vm"),
)
@click.option(
    "-y",
    "--yes",
    "assume_yes",
    is_flag=True,
    help=tr("removemount.option_yes"),
)
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def removemount_command(
    source_dir: Optional[Path],
    vm_name: Optional[str],
    assume_yes: bool,
    config_path: Optional[str],
    non_interactive: bool,
) -> None:
    """Remove a mount entry from the YAML config."""
    interactive = is_interactive_terminal() and not non_interactive

    resolved_config_path = resolve_config_path(Path(config_path) if config_path else None)
    if not resolved_config_path.exists():
        raise click.ClickException(tr("config.file_not_found", path=resolved_config_path))

    yaml, config_data = _load_config_with_comments(resolved_config_path)
    mounts_section = config_data.get("mounts")
    if mounts_section is None:
        raise click.ClickException(tr("removemount.none_configured"))
    if not isinstance(mounts_section, list):
        raise click.ClickException(tr("config.mounts_not_list"))

    try:
        mounts = load_mounts_config(config_data)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    mount_index, selected_mount = _select_mount(mounts, source_dir, vm_name, interactive)

    click.echo(
        tr(
            "removemount.summary",
            source=selected_mount.source,
            vm_name=selected_mount.vm_name,
            target=selected_mount.target,
        )
    )

    if not assume_yes:
        if not interactive:
            raise click.ClickException(tr("removemount.confirm_required"))
        if not click.confirm(tr("removemount.confirm_remove", path=resolved_config_path), default=True):
            click.echo(tr("removemount.cancelled"))
            return

    try:
        umount_directory(selected_mount)
    except MultipassError as exc:
        raise click.ClickException(str(exc))
    click.echo(tr("mounts.unmounted", vm_name=selected_mount.vm_name, target=selected_mount.target))

    del mounts_section[mount_index]

    config_backup_path = _backup_config(resolved_config_path)
    with resolved_config_path.open("w", encoding="utf-8") as handle:
        yaml.dump(config_data, handle)

    click.echo(tr("removemount.backup_created", path=config_backup_path))
    click.echo(tr("removemount.removed", path=resolved_config_path))
