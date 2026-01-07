from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import click

from ..config import ConfigError, load_config, load_vms_config, resolve_config_path
from ..vm import MultipassError, ensure_multipass_available
from . import non_interactive_option


def _start_vm(vm_name: str) -> None:
    result = subprocess.run(
        ["multipass", "start", vm_name], check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        details = f": {stderr}" if stderr else ""
        raise MultipassError(f"Не удалось запустить ВМ `{vm_name}`{details}")


@click.command(name="start-vm")
@non_interactive_option
@click.argument("vm_name", required=False)
@click.option("--all-vms", is_flag=True, help="Запустить все ВМ из конфигурации")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию ~/.config/agsekit/config.yaml или $CONFIG_PATH).",
)
def start_vm_command(
    vm_name: Optional[str],
    all_vms: bool,
    config_path: Optional[str],
    non_interactive: bool,
) -> None:
    """Запускает одну или все Multipass ВМ."""

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if all_vms and vm_name:
        raise click.ClickException("Не указывайте имя ВМ вместе с флагом --all-vms")

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
                raise click.ClickException("Укажите имя ВМ или используйте флаг --all-vms")
        if target_vm not in vms:
            raise click.ClickException(f"ВМ `{target_vm}` отсутствует в конфигурации")
        targets = [target_vm]

    try:
        ensure_multipass_available()
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    for target in targets:
        click.echo(f"Запускается ВМ `{target}`...")
        try:
            _start_vm(target)
        except MultipassError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"ВМ `{target}` запущена.")
