from __future__ import annotations

import subprocess
from pathlib import Path

import click

from ..config import ConfigError, load_config, load_vms_config, resolve_config_path
from ..vm import MultipassError, ensure_multipass_available
from . import non_interactive_option


def _stop_vm(vm_name: str) -> None:
    result = subprocess.run(
        ["multipass", "stop", vm_name], check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        details = f": {stderr}" if stderr else ""
        raise MultipassError(f"Не удалось остановить ВМ `{vm_name}`{details}")


@click.command(name="stop")
@non_interactive_option
@click.argument("vm_name", required=False)
@click.option("--all-vms", is_flag=True, help="Остановить все ВМ из конфигурации")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию ~/.config/agsekit/config.yaml или $CONFIG_PATH).",
)
def stop_command(vm_name: str | None, all_vms: bool, config_path: str | None, non_interactive: bool) -> None:
    """Останавливает одну или все Multipass ВМ."""

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
        if not vm_name:
            raise click.ClickException("Укажите имя ВМ или используйте флаг --all-vms")
        if vm_name not in vms:
            raise click.ClickException(f"ВМ `{vm_name}` отсутствует в конфигурации")
        targets = [vm_name]

    try:
        ensure_multipass_available()
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    for target in targets:
        click.echo(f"Останавливается ВМ `{target}`...")
        try:
            _stop_vm(target)
        except MultipassError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"ВМ `{target}` остановлена.")
