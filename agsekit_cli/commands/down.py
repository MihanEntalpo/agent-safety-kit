from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click

from ..agents_modules import get_agent_class
from ..agents import configured_agent_vms
from ..config import (
    AgentConfig,
    ConfigError,
    MountConfig,
    load_agents_config,
    load_config,
    load_mounts_config,
    load_vms_config,
    resolve_config_path,
)
from ..debug import debug_scope
from ..interactive import is_interactive_terminal
from ..i18n import tr
from ..vm import MultipassError, ensure_multipass_available
from . import debug_option, non_interactive_option
from .status import _collect_running_agent_processes
from .stop import _read_vm_state, _stop_vm, _unmount_vm_mounts
from ..daemon_backends import stop_portforward_daemon


def _collect_running_configured_agents(vm_names: List[str], agents: Dict[str, AgentConfig]) -> List[Tuple[str, str, str, str]]:
    agents_by_vm: Dict[str, List[AgentConfig]] = {vm_name: [] for vm_name in vm_names}
    for agent in agents.values():
        for vm_name in configured_agent_vms(agent, vm_names):
            agents_by_vm[vm_name].append(agent)

    running_agents: List[Tuple[str, str, str, str]] = []
    for vm_name in vm_names:
        vm_agents = agents_by_vm.get(vm_name, [])
        if not vm_agents:
            continue

        binary_to_names: Dict[str, List[str]] = {}
        for agent in vm_agents:
            runtime_binary = get_agent_class(agent.type).runtime_binary
            binary_to_names.setdefault(runtime_binary, []).append(agent.name)

        running_processes = _collect_running_agent_processes(vm_name, list(binary_to_names.keys()))
        if not running_processes:
            continue

        for _pid, binary, cwd in running_processes:
            config_names = sorted(binary_to_names.get(binary, [binary]))
            names = ", ".join(config_names)
            running_agents.append((vm_name, names, binary, cwd or tr("status.cwd_unknown")))

    return running_agents


def _report_running_agents(running_agents: List[Tuple[str, str, str, str]]) -> None:
    click.echo(click.style(tr("down.running_agents_header"), bold=True))
    for vm_name, names, binary, cwd in running_agents:
        click.echo(tr("down.running_agent_line", vm_name=vm_name, names=names, binary=binary, cwd=cwd))


def _shutdown_vms(targets: List[str], mounts: List[MountConfig], *, debug: bool) -> None:
    for target in targets:
        state = _read_vm_state(target, debug=debug)
        if state == "absent":
            click.echo(tr("down.vm_absent", vm_name=target))
            continue
        if state in {"stopped", "suspended"}:
            click.echo(tr("down.vm_already_stopped", vm_name=target))
            continue

        _unmount_vm_mounts(target, mounts, debug=debug)
        click.echo(tr("down.stopping", vm_name=target))
        _stop_vm(target, debug=debug)
        click.echo(tr("down.stopped", vm_name=target))


@click.command(name="down", help=tr("down.command_help"))
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
@click.option("-f", "--force", is_flag=True, help=tr("down.option_force"))
@debug_option
def down_command(
    config_path: Optional[str],
    force: bool,
    debug: bool,
    non_interactive: bool,
) -> None:
    """Stop all configured VMs, optionally confirming if agents are still running."""
    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
        mounts = load_mounts_config(config)
        agents = load_agents_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    targets = list(vms.keys())

    with debug_scope(debug):
        try:
            ensure_multipass_available()
        except MultipassError as exc:
            raise click.ClickException(str(exc))

        if not force:
            running_agents = _collect_running_configured_agents(targets, agents)
            if running_agents:
                _report_running_agents(running_agents)
                if non_interactive or not is_interactive_terminal():
                    raise click.ClickException(tr("down.confirmation_required"))
                if not click.confirm(tr("down.confirm_prompt"), default=False):
                    click.echo(tr("down.cancelled"))
                    return

        try:
            stop_portforward_daemon(announce=debug)
            _shutdown_vms(targets, mounts, debug=debug)
        except MultipassError as exc:
            raise click.ClickException(str(exc))
