from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
from typing import Optional

import click
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError

from . import non_interactive_option
from ..config import (
    ConfigError,
    MountConfig,
    default_mount_backup,
    default_mount_target,
    load_mounts_config,
    load_vms_config,
    resolve_config_path,
)
from ..i18n import tr
from ..interactive import is_interactive_terminal
from ..mounts import MountAlreadyMountedError, find_mount_by_source, mount_directory, normalize_path
from ..vm import MultipassError


def _prompt_positive_int(message: str, default: int, error_key: str) -> int:
    while True:
        value = click.prompt(message, default=default, type=int)
        if value > 0:
            return value
        click.echo(tr(error_key))


def _parse_interval(raw_value: Optional[str]) -> int:
    if raw_value is None:
        return 5
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise click.ClickException(tr("addmount.interval_not_int")) from exc
    if value <= 0:
        raise click.ClickException(tr("addmount.interval_positive"))
    return value


def _parse_max_backups(raw_value: Optional[int]) -> int:
    if raw_value is None:
        return 100
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise click.ClickException(tr("addmount.max_backups_not_int")) from exc
    if value <= 0:
        raise click.ClickException(tr("addmount.max_backups_positive"))
    return value


def _prompt_backup_clean_method(default: str) -> str:
    return click.prompt(
        tr("addmount.backup_clean_method_prompt"),
        default=default,
        type=click.Choice(["tail", "thin"], case_sensitive=False),
    )


def _load_config_with_comments(config_path: Path) -> tuple[YAML, CommentedMap]:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.load(handle)
    except YAMLError as exc:
        raise click.ClickException(tr("addmount.config_parse_failed", path=config_path, error=exc)) from exc

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


@click.command(name="addmount", help=tr("addmount.command_help"))
@non_interactive_option
@click.argument("source_dir", required=False, type=click.Path(file_okay=False, path_type=Path))
@click.argument("target_dir", required=False, type=click.Path(path_type=Path))
@click.argument("backup_dir", required=False, type=click.Path(path_type=Path))
@click.argument("interval", required=False)
@click.option(
    "--max-backups",
    type=int,
    default=None,
    help=tr("addmount.option_max_backups"),
)
@click.option(
    "--backup-clean-method",
    type=click.Choice(["tail", "thin"], case_sensitive=False),
    default=None,
    help=tr("addmount.option_backup_clean_method"),
)
@click.option(
    "--mount",
    "mount_now",
    is_flag=True,
    help=tr("addmount.option_mount"),
)
@click.option(
    "-y",
    "--yes",
    "assume_yes",
    is_flag=True,
    help=tr("addmount.option_yes"),
)
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def addmount_command(
    source_dir: Optional[Path],
    target_dir: Optional[Path],
    backup_dir: Optional[Path],
    interval: Optional[str],
    max_backups: Optional[int],
    backup_clean_method: Optional[str],
    mount_now: bool,
    assume_yes: bool,
    config_path: Optional[str],
    non_interactive: bool,
) -> None:
    """Add a mount entry to the YAML config."""
    interactive = is_interactive_terminal() and not non_interactive

    if source_dir is None:
        if not interactive:
            raise click.ClickException(tr("addmount.source_required"))
        source_prompt = click.prompt(tr("addmount.source_prompt"), default=str(Path.cwd()))
        source_dir = Path(source_prompt).expanduser()

    source_dir = normalize_path(source_dir)

    if target_dir is None:
        default_target = default_mount_target(source_dir)
        if interactive:
            target_prompt = click.prompt(tr("addmount.target_prompt"), default=str(default_target))
            target_dir = Path(target_prompt).expanduser()
        else:
            target_dir = default_target

    if backup_dir is None:
        default_backup = default_mount_backup(source_dir)
        if interactive:
            backup_prompt = click.prompt(tr("addmount.backup_prompt"), default=str(default_backup))
            backup_dir = Path(backup_prompt).expanduser()
        else:
            backup_dir = default_backup

    target_dir = target_dir.expanduser().resolve()
    backup_dir = backup_dir.expanduser().resolve()

    if interval is None and interactive:
        interval_minutes = _prompt_positive_int(
            tr("addmount.interval_prompt"),
            default=5,
            error_key="addmount.interval_positive",
        )
    else:
        interval_minutes = _parse_interval(interval)

    if max_backups is None and interactive:
        max_backups_value = _prompt_positive_int(
            tr("addmount.max_backups_prompt"),
            default=100,
            error_key="addmount.max_backups_positive",
        )
    else:
        max_backups_value = _parse_max_backups(max_backups)

    if backup_clean_method is None and interactive:
        backup_clean_method_value = _prompt_backup_clean_method("thin")
    else:
        backup_clean_method_value = (backup_clean_method or "thin").lower()

    resolved_config_path = resolve_config_path(Path(config_path) if config_path else None)
    if not resolved_config_path.exists():
        raise click.ClickException(tr("config.file_not_found", path=resolved_config_path))

    yaml, config_data = _load_config_with_comments(resolved_config_path)

    try:
        vms = load_vms_config(config_data)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    try:
        existing_mounts = load_mounts_config(config_data)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if find_mount_by_source(existing_mounts, source_dir) is not None:
        raise click.ClickException(tr("addmount.mount_exists", source=source_dir))

    click.echo(
        tr(
            "addmount.summary",
            source=source_dir,
            target=target_dir,
            backup=backup_dir,
            interval=interval_minutes,
            max_backups=max_backups_value,
            method=backup_clean_method_value,
        )
    )

    if not assume_yes:
        if not interactive:
            raise click.ClickException(tr("addmount.confirm_required"))
        if not click.confirm(tr("addmount.confirm_add", path=resolved_config_path), default=True):
            click.echo(tr("addmount.cancelled"))
            return

    mounts_section = config_data.get("mounts")
    if mounts_section is None:
        mounts_section = CommentedSeq()
        config_data["mounts"] = mounts_section
    if not isinstance(mounts_section, list):
        raise click.ClickException(tr("config.mounts_not_list"))

    mount_entry = CommentedMap()
    mount_entry["source"] = str(source_dir)
    mount_entry["target"] = str(target_dir)
    mount_entry["backup"] = str(backup_dir)
    mount_entry["interval"] = interval_minutes
    mount_entry["max_backups"] = max_backups_value
    mount_entry["backup_clean_method"] = backup_clean_method_value
    mounts_section.append(mount_entry)

    config_backup_path = _backup_config(resolved_config_path)

    with resolved_config_path.open("w", encoding="utf-8") as handle:
        yaml.dump(config_data, handle)

    click.echo(tr("addmount.backup_created", path=config_backup_path))
    click.echo(tr("addmount.added", path=resolved_config_path))

    if interactive and not mount_now:
        mount_now = click.confirm(tr("addmount.mount_now_prompt"), default=False)

    if mount_now:
        default_vm = next(iter(vms.keys()))
        try:
            mount_directory(
                MountConfig(
                    source=source_dir,
                    target=target_dir,
                    backup=backup_dir,
                    interval_minutes=interval_minutes,
                    max_backups=max_backups_value,
                    backup_clean_method=backup_clean_method_value,
                    vm_name=default_vm,
                )
            )
        except MountAlreadyMountedError:
            click.echo(
                tr(
                    "mounts.already_mounted",
                    source=normalize_path(source_dir),
                    vm_name=default_vm,
                    target=target_dir,
                )
            )
        except MultipassError as exc:
            raise click.ClickException(str(exc))
        else:
            click.echo(
                tr(
                    "mounts.mounted",
                    source=normalize_path(source_dir),
                    vm_name=default_vm,
                    target=target_dir,
                )
            )
