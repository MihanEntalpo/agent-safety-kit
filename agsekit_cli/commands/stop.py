from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import click

from ..config import ConfigError, load_config, load_vms_config, resolve_config_path
from ..i18n import tr
from ..vm import MultipassError, ensure_multipass_available
from . import non_interactive_option


def _stop_vm(vm_name: str) -> None:
    result = subprocess.run(
        ["multipass", "stop", vm_name], check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        details = f": {stderr}" if stderr else ""
        raise MultipassError(tr("stop_vm.stop_failed", vm_name=vm_name, details=details))


@click.command(name="stop-vm", help=tr("stop_vm.command_help"))
@non_interactive_option
@click.argument("vm_name", required=False)
@click.option("--all-vms", is_flag=True, help=tr("stop_vm.option_all"))
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def stop_vm_command(vm_name: Optional[str], all_vms: bool, config_path: Optional[str], non_interactive: bool) -> None:
    """Останавливает одну или все Multipass ВМ."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if all_vms and vm_name:
        raise click.ClickException(tr("stop_vm.name_with_all"))

    targets: list[str]
    if all_vms:
        targets = list(vms.keys())
    else:
        target_vm = vm_name
        if not target_vm:
            if len(vms) == 1:
                target_vm = next(iter(vms.keys()))
                click.echo(tr("stop_vm.default_vm", vm_name=target_vm))
            else:
                raise click.ClickException(tr("stop_vm.name_required"))
        if target_vm not in vms:
            raise click.ClickException(tr("stop_vm.vm_missing", vm_name=target_vm))
        targets = [target_vm]

    try:
        ensure_multipass_available()
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    for target in targets:
        click.echo(tr("stop_vm.stopping", vm_name=target))
        try:
            _stop_vm(target)
        except MultipassError as exc:
            raise click.ClickException(str(exc))
        click.echo(tr("stop_vm.stopped", vm_name=target))
