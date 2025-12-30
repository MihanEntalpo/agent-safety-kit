from __future__ import annotations

from pathlib import Path

import click

from . import non_interactive_option

from ..config import ConfigError, load_config, load_vms_config, resolve_config_path
from ..vm import MultipassError, create_all_vms_from_config, create_vm_from_config


@click.command(name="create-vm")
@non_interactive_option
@click.argument("vm_name", required=False)
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Path to the YAML config (defaults to ~/.config/agsekit/config.yaml or $CONFIG_PATH).",
)
def create_vm_command(vm_name: str | None, config_path: str | None, non_interactive: bool) -> None:
    """Create a single VM by name from the YAML configuration."""

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)

    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    target_vm = vm_name
    if not target_vm:
        if len(vms) == 1:
            target_vm = next(iter(vms.keys()))
            click.echo(f"Имя ВМ не указано: используется единственная ВМ `{target_vm}` из конфигурации.")
        else:
            raise click.ClickException("Укажите имя ВМ или запустите create-vms для создания всех машин.")

    click.echo(f"Creating VM `{target_vm}` from {resolved_path}...")
    try:
        message = create_vm_from_config(str(resolved_path), target_vm)
    except ConfigError as exc:
        raise click.ClickException(str(exc))
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    click.echo(message)


@click.command(name="create-vms")
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Path to the YAML config (defaults to ~/.config/agsekit/config.yaml or $CONFIG_PATH).",
)
def create_vms_command(config_path: str | None, non_interactive: bool) -> None:
    """Create all VMs described in the YAML configuration."""

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    click.echo(f"Creating every VM defined in {resolved_path}...")
    try:
        messages = create_all_vms_from_config(str(resolved_path))
    except ConfigError as exc:
        raise click.ClickException(str(exc))
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    for message in messages:
        click.echo(message)
