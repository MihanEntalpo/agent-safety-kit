from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from ..config import ConfigError, load_config, load_mounts_config, load_vms_config, resolve_config_path
from ..debug import debug_scope
from ..i18n import tr
from ..vm import MultipassError, ensure_multipass_available
from . import debug_option, non_interactive_option
from .start_vm import _start_vm
from .stop import _stop_vm, _unmount_vm_mounts


@click.command(name="restart-vm", help=tr("restart_vm.command_help"))
@non_interactive_option
@click.argument("vm_name", required=False)
@click.option("--all-vms", is_flag=True, help=tr("restart_vm.option_all"))
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
@debug_option
def restart_vm_command(
    vm_name: Optional[str],
    all_vms: bool,
    config_path: Optional[str],
    debug: bool,
    non_interactive: bool,
) -> None:
    """Перезапускает одну или все Multipass ВМ."""
    del non_interactive

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
        mounts = load_mounts_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if all_vms and vm_name:
        raise click.ClickException(tr("restart_vm.name_with_all"))

    targets: list[str]
    if all_vms:
        targets = list(vms.keys())
    else:
        target_vm = vm_name
        if not target_vm:
            if len(vms) == 1:
                target_vm = next(iter(vms.keys()))
                click.echo(tr("restart_vm.default_vm", vm_name=target_vm))
            else:
                raise click.ClickException(tr("restart_vm.name_required"))
        if target_vm not in vms:
            raise click.ClickException(tr("restart_vm.vm_missing", vm_name=target_vm))
        targets = [target_vm]

    with debug_scope(debug):
        try:
            ensure_multipass_available()
        except MultipassError as exc:
            raise click.ClickException(str(exc))

        for target in targets:
            try:
                _unmount_vm_mounts(target, mounts, debug=debug)
                click.echo(tr("restart_vm.stopping", vm_name=target))
                _stop_vm(target, debug=debug)
            except MultipassError as exc:
                raise click.ClickException(str(exc))

        for target in targets:
            click.echo(tr("restart_vm.starting", vm_name=target))
            try:
                _start_vm(target, debug=debug)
            except MultipassError as exc:
                raise click.ClickException(str(exc))
            click.echo(tr("restart_vm.restarted", vm_name=target))
