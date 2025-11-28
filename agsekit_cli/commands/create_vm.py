from __future__ import annotations

from pathlib import Path

import click

from ..config import ConfigError, resolve_config_path
from ..vm import MultipassError, create_vm_from_config


@click.command(name="create-vm")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию config.yaml или $CONFIG_PATH).",
)
def create_vm_command(config_path: str | None) -> None:
    """Создает ВМ по конфигурации из YAML."""

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        message = create_vm_from_config(str(resolved_path))
    except ConfigError as exc:
        raise click.ClickException(str(exc))
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    click.echo(message)
