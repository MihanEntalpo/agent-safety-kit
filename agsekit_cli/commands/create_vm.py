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
    help="Path to the YAML config (defaults to config.yaml or $CONFIG_PATH).",
)
def create_vm_command(vm_name: str, config_path: str | None) -> None:
    """Create a single VM by name from the YAML configuration."""

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    click.echo(f"Creating VM `{vm_name}` from {resolved_path}...")
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
    help="Path to the YAML config (defaults to config.yaml or $CONFIG_PATH).",
)
def create_vms_command(config_path: str | None) -> None:
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
