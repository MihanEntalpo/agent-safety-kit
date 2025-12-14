from __future__ import annotations

from pathlib import Path

import click

from ..config import ConfigError, resolve_config_path
from ..vm import MultipassError, create_all_vms_from_config, create_vm_from_config


@click.command(name="create-vm")
@click.argument("vm_name")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию config.yaml или $CONFIG_PATH).",
)
def create_vm_command(vm_name: str, config_path: str | None) -> None:
    """Создает одну ВМ по имени из YAML-конфигурации."""

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        message = create_vm_from_config(str(resolved_path), vm_name)
    except ConfigError as exc:
        raise click.ClickException(str(exc))
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    click.echo(message)


@click.command(name="create-vms")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию config.yaml или $CONFIG_PATH).",
)
def create_vms_command(config_path: str | None) -> None:
    """Создает все ВМ, описанные в YAML-конфигурации."""

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        messages = create_all_vms_from_config(str(resolved_path))
    except ConfigError as exc:
        raise click.ClickException(str(exc))
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    for message in messages:
        click.echo(message)
