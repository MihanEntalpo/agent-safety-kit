from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from . import non_interactive_option

from ..config import ConfigError, load_config, load_vms_config, resolve_config_path
from ..i18n import tr
from ..vm import MultipassError, create_all_vms_from_config, create_vm_from_config
from ..vm_prepare import ensure_host_ssh_keypair, prepare_vm


@click.command(name="create-vm", help=tr("create_vm.command_help"))
@non_interactive_option
@click.argument("vm_name", required=False)
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def create_vm_command(vm_name: Optional[str], config_path: Optional[str], non_interactive: bool) -> None:
    """Create a single VM by name from the YAML configuration."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

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
            click.echo(tr("create_vm.default_vm", vm_name=target_vm))
        else:
            raise click.ClickException(tr("create_vm.name_required"))

    click.echo(tr("create_vm.creating", vm_name=target_vm, config_path=resolved_path))
    try:
        result = create_vm_from_config(str(resolved_path), target_vm)
    except ConfigError as exc:
        raise click.ClickException(str(exc))
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    if isinstance(result, tuple):
        message, mismatch_message = result
    else:
        message = result
        mismatch_message = None

    click.echo(message)
    click.echo(tr("prepare.ensure_keypair"))
    _private_key, public_key = ensure_host_ssh_keypair()
    bundles = vms[target_vm].install
    if bundles:
        prepare_vm(target_vm, public_key, bundles)
    else:
        prepare_vm(target_vm, public_key)
    if mismatch_message:
        click.echo(mismatch_message)


@click.command(name="create-vms", help=tr("create_vm.command_all_help"))
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def create_vms_command(config_path: Optional[str], non_interactive: bool) -> None:
    """Create all VMs described in the YAML configuration."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    click.echo(tr("create_vm.creating_all", config_path=resolved_path))
    try:
        messages, mismatch_messages = create_all_vms_from_config(str(resolved_path))
    except ConfigError as exc:
        raise click.ClickException(str(exc))
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    for message in messages:
        click.echo(message)

    click.echo(tr("prepare.ensure_keypair"))
    _private_key, public_key = ensure_host_ssh_keypair()
    for vm in vms.values():
        prepare_vm(vm.name, public_key, vm.install)
    for mismatch in mismatch_messages:
        click.echo(mismatch)
