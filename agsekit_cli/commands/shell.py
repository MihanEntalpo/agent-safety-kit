from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict

import click
import questionary

from ..config import ConfigError, load_config, load_vms_config, resolve_config_path
from ..interactive import is_interactive_terminal
from ..vm import MultipassError, ensure_multipass_available
from . import non_interactive_option


def _select_vm(vms: Dict[str, object]) -> str:
    choices = [questionary.Choice(name, value=name) for name in vms]
    selected = questionary.select("Выберите ВМ для запуска shell:", choices=choices, use_shortcuts=True).ask()
    if selected is None:
        raise click.Abort()
    return str(selected)


@click.command(name="shell")
@non_interactive_option
@click.argument("vm_name", required=False)
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию ~/.config/agsekit/config.yaml или $CONFIG_PATH).",
)
def shell_command(vm_name: str | None, config_path: str | None, non_interactive: bool) -> None:
    """Открывает интерактивный shell в Multipass ВМ."""

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    target_vm = vm_name
    if not target_vm:
        vm_names = list(vms.keys())
        if len(vm_names) == 1:
            target_vm = vm_names[0]
        else:
            if non_interactive or not is_interactive_terminal():
                raise click.ClickException(
                    "Укажите имя ВМ для подключения или запустите команду в интерактивном терминале."
                )
            target_vm = _select_vm(vms)

    if target_vm not in vms:
        raise click.ClickException(f"ВМ `{target_vm}` отсутствует в конфигурации")

    try:
        ensure_multipass_available()
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    click.echo(f"Opening shell in VM `{target_vm}`...")
    result = subprocess.run(["multipass", "shell", target_vm], check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
