from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import click

from ..config import ConfigError, load_agents_config, load_config, load_vms_config, resolve_config_path
from ..debug import debug_scope
from ..i18n import tr
from ..interactive import is_interactive_terminal
from ..vm import (
    MultipassError,
    _start_vm_after_resize,
    _stop_vm_for_resize,
    apply_vm_cpu_ram,
    ensure_multipass_available,
    ensure_resize_resources_available,
    fetch_existing_info,
    get_vm_state,
    vm_mismatch_details,
)
from . import debug_option, non_interactive_option
from .down import _collect_running_configured_agents, _report_running_agents


@click.command(name="update-vm", help=tr("update_vm.command_help"))
@non_interactive_option
@click.argument("vm_name", required=False)
@click.option("--all-vms", is_flag=True, help=tr("update_vm.option_all"))
@click.option("-f", "--force", is_flag=True, help=tr("update_vm.option_force"))
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
@debug_option
def update_vm_command(
    vm_name: Optional[str],
    all_vms: bool,
    force: bool,
    config_path: Optional[str],
    debug: bool,
    non_interactive: bool,
) -> None:
    """Apply configured CPU and RAM limits to existing Multipass VMs."""

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
        agents = load_agents_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if all_vms and vm_name:
        raise click.ClickException(tr("update_vm.name_with_all"))
    if all_vms:
        targets = list(vms.keys())
    else:
        target = vm_name
        if not target:
            if len(vms) == 1:
                target = next(iter(vms))
                click.echo(tr("update_vm.default_vm", vm_name=target))
            else:
                raise click.ClickException(tr("update_vm.name_required"))
        if target not in vms:
            raise click.ClickException(tr("update_vm.vm_missing", vm_name=target))
        targets = [target]

    with debug_scope(debug):
        try:
            ensure_multipass_available()
            for target in targets:
                existing_info = fetch_existing_info()
                state = get_vm_state(existing_info, target)
                if state is None:
                    click.echo(tr("update_vm.vm_absent", vm_name=target))
                    continue
                if state == "suspended":
                    click.echo(tr("vm.resize_suspended", vm_name=target))
                    continue

                changes = [item for item in vm_mismatch_details(existing_info, vms[target]) if item in {"cpus", "memory"}]
                if not changes:
                    click.echo(tr("update_vm.already_matches", vm_name=target))
                    continue

                was_running = state == "running"
                if was_running:
                    running_agents = _collect_running_configured_agents([target], agents)
                    if running_agents:
                        _report_running_agents(running_agents)
                    if not force:
                        if non_interactive or not is_interactive_terminal():
                            raise click.ClickException(tr("update_vm.confirmation_required", vm_name=target))
                        if not click.confirm(tr("update_vm.confirm_prompt", vm_name=target), default=False):
                            click.echo(tr("update_vm.cancelled", vm_name=target))
                            continue
                    click.echo(tr("update_vm.stopping", vm_name=target))
                    _stop_vm_for_resize(target)

                try:
                    stopped_info = fetch_existing_info()
                    ensure_resize_resources_available(stopped_info, vms[target])
                    applied = apply_vm_cpu_ram(vms[target], stopped_info)
                finally:
                    if was_running:
                        click.echo(tr("update_vm.starting", vm_name=target))
                        _start_vm_after_resize(target)

                click.echo(tr("update_vm.updated", vm_name=target, details=", ".join(applied)))
        except MultipassError as exc:
            raise click.ClickException(str(exc))
