from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import click

from ..config import ConfigError, load_config, load_vms_config, resolve_config_path
from ..interactive import is_interactive_terminal
from ..vm import MultipassError, ensure_multipass_available
from . import non_interactive_option


def _delete_vm(vm_name: str) -> None:
    result = subprocess.run(
        ["multipass", "delete", vm_name], check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        details = f": {stderr}" if stderr else ""
        raise MultipassError(f"Не удалось удалить ВМ `{vm_name}`{details}")


def _purge_deleted() -> None:
    result = subprocess.run(["multipass", "purge"], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        details = f": {stderr}" if stderr else ""
        raise MultipassError(f"Не удалось очистить удаленные ВМ{details}")


@click.command(name="destroy-vm")
@non_interactive_option
@click.argument("vm_name", required=False)
@click.option("--all", "all_vms", is_flag=True, help="Удалить все ВМ из конфигурации")
@click.option("-y", "yes", is_flag=True, help="Подтвердить удаление без запроса")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию ~/.config/agsekit/config.yaml или $CONFIG_PATH).",
)
def destroy_vm_command(
    vm_name: Optional[str],
    all_vms: bool,
    yes: bool,
    config_path: Optional[str],
    non_interactive: bool,
) -> None:
    """Удаляет одну или все Multipass ВМ."""

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if all_vms and vm_name:
        raise click.ClickException("Не указывайте имя ВМ вместе с флагом --all")

    targets: list[str]
    if all_vms:
        targets = list(vms.keys())
    else:
        target_vm = vm_name
        if not target_vm:
            if len(vms) == 1:
                target_vm = next(iter(vms.keys()))
                click.echo(f"Имя ВМ не указано: используется единственная ВМ `{target_vm}` из конфигурации.")
            else:
                raise click.ClickException("Укажите имя ВМ или используйте флаг --all")
        if target_vm not in vms:
            raise click.ClickException(f"ВМ `{target_vm}` отсутствует в конфигурации")
        targets = [target_vm]

    if not yes:
        if not is_interactive_terminal():
            raise click.ClickException("Удаление требует подтверждения. Повторите команду с флагом -y.")
        if all_vms:
            label = "все ВМ из конфигурации"
        elif len(targets) == 1:
            label = f"ВМ `{targets[0]}`"
        else:
            label = ", ".join(targets)
        if not click.confirm(f"Подтвердите удаление {label}", default=False):
            click.echo("Удаление отменено.")
            return

    try:
        ensure_multipass_available()
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    for target in targets:
        click.echo(f"Удаляется ВМ `{target}`...")
        try:
            _delete_vm(target)
        except MultipassError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"ВМ `{target}` удалена.")

    try:
        _purge_deleted()
    except MultipassError as exc:
        raise click.ClickException(str(exc))
