from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Optional

import click

from ..config import ConfigError, load_config, load_vms_config, resolve_config_path
from ..debug import debug_log_command, debug_log_result, debug_scope
from ..i18n import tr
from ..vm import MultipassError, ensure_multipass_available
from . import debug_option, non_interactive_option

STOP_VM_GRACEFUL_TIMEOUT_SECONDS = 30


def _run_multipass_command(command: list[str], *, debug: bool = False) -> subprocess.CompletedProcess[str]:
    debug_log_command(command, enabled=debug)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    debug_log_result(result, enabled=debug)
    return result


def _read_vm_state(vm_name: str, *, debug: bool = False) -> Optional[str]:
    result = _run_multipass_command(["multipass", "list", "--format", "json"], debug=debug)
    if result.returncode != 0:
        return None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    instances = payload.get("list")
    if not isinstance(instances, list):
        return None

    for item in instances:
        if not isinstance(item, dict):
            continue
        if item.get("name") != vm_name:
            continue
        state = item.get("state")
        if state is None:
            return None
        return str(state).strip().lower()
    return None


def _stop_vm(vm_name: str, *, debug: bool = False) -> None:
    poweroff_result = _run_multipass_command(
        ["multipass", "exec", vm_name, "--", "sudo", "poweroff"],
        debug=debug,
    )

    time.sleep(STOP_VM_GRACEFUL_TIMEOUT_SECONDS)
    state = _read_vm_state(vm_name, debug=debug)
    if state in {"stopped", "suspended"}:
        return

    force_result = _run_multipass_command(["multipass", "stop", "--force", vm_name], debug=debug)
    if force_result.returncode != 0:
        stderr = force_result.stderr.strip() or force_result.stdout.strip()
        if not stderr and poweroff_result.returncode != 0:
            stderr = poweroff_result.stderr.strip() or poweroff_result.stdout.strip()
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
@debug_option
def stop_vm_command(
    vm_name: Optional[str],
    all_vms: bool,
    config_path: Optional[str],
    debug: bool,
    non_interactive: bool,
) -> None:
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

    with debug_scope(debug):
        try:
            ensure_multipass_available()
        except MultipassError as exc:
            raise click.ClickException(str(exc))

        for target in targets:
            click.echo(tr("stop_vm.stopping", vm_name=target))
            try:
                _stop_vm(target, debug=debug)
            except MultipassError as exc:
                raise click.ClickException(str(exc))
            click.echo(tr("stop_vm.stopped", vm_name=target))
