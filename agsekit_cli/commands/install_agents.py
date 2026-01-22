from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import click

from ..agents import find_agent
from ..config import AgentConfig, ConfigError, VmConfig, load_agents_config, load_config, load_vms_config, resolve_config_path
from ..i18n import tr
from ..vm import MultipassError, ensure_multipass_available, resolve_proxychains
from . import non_interactive_option

PLAYBOOKS_DIR = Path(__file__).resolve().parents[1] / "ansible" / "agents"


def _playbook_for(agent: AgentConfig) -> Path:
    candidate = PLAYBOOKS_DIR / f"{agent.type}.yml"
    if not candidate.exists():
        raise ConfigError(tr("install_agents.script_missing", agent_type=agent.type, path=candidate))
    return candidate


def _format_command(command: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _log_failed_command(
    command: List[str],
    result: subprocess.CompletedProcess[str],
    description: str,
) -> None:
    click.echo(tr("install_agents.command_failed", description=description, code=result.returncode), err=True)
    click.echo(tr("install_agents.command_label", command=_format_command(command)), err=True)
    stdout = result.stdout.strip() if result.stdout else ""
    stderr = result.stderr.strip() if result.stderr else ""
    if stdout:
        click.echo(tr("install_agents.stdout_label", output=stdout), err=True)
    if stderr:
        click.echo(tr("install_agents.stderr_label", output=stderr), err=True)


def _run_command(
    command: List[str],
    description: str,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    click.echo(tr("install_agents.command_running", description=description, command=_format_command(command)))
    if capture_output:
        return subprocess.run(command, check=False, capture_output=True, text=True)
    return subprocess.run(command, check=False, text=True)


def _run_install_playbook(vm: VmConfig, playbook_path: Path, proxychains: Optional[str] = None) -> None:
    ensure_multipass_available()
    effective_proxychains = resolve_proxychains(vm, proxychains)
    install_command = [
        "ansible-playbook",
        "-i",
        "localhost,",
        "-e",
        f"vm_name={vm.name}",
    ]
    if effective_proxychains:
        install_command.extend(["-e", f"proxychains_url={effective_proxychains}"])
    install_command.append(str(playbook_path))
    result = _run_command(
        install_command,
        tr("install_agents.run_installer", script=playbook_path.name, vm_name=vm.name),
        capture_output=False,
    )
    if result.returncode != 0:
        _log_failed_command(install_command, result, tr("install_agents.installer_execution_label"))
        raise MultipassError(tr("install_agents.install_failed", vm_name=vm.name, code=result.returncode))


def _default_vm(agent: AgentConfig, available: Iterable[str]) -> str:
    if agent.vm_name:
        return agent.vm_name
    try:
        return next(iter(available))
    except StopIteration:
        raise ConfigError(tr("install_agents.no_vms_available"))


@click.command(name="install-agents", help=tr("install_agents.command_help"))
@non_interactive_option
@click.argument("agent_name", required=False)
@click.argument("vm", required=False)
@click.option("--all-vms", is_flag=True, help=tr("install_agents.option_all_vms"))
@click.option("--all-agents", is_flag=True, help=tr("install_agents.option_all_agents"))
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
@click.option(
    "--proxychains",
    default=None,
    show_default=False,
    help=tr("install_agents.option_proxychains"),
)
def install_agents_command(
    agent_name: Optional[str],
    vm: Optional[str],
    all_vms: bool,
    all_agents: bool,
    config_path: Optional[str],
    proxychains: Optional[str],
    non_interactive: bool,
) -> None:
    """Install configured agents into Multipass VMs."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    click.echo(tr("install_agents.preparing"))

    if all_agents and agent_name:
        raise click.ClickException(tr("install_agents.agent_conflict"))

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        agents_config = load_agents_config(config)
        vms_config = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if not agents_config:
        raise click.ClickException(tr("install_agents.no_agents"))

    agent_names: List[str]
    if all_agents:
        agent_names = list(agents_config.keys())
    else:
        if agent_name:
            agent_names = [agent_name]
        elif len(agents_config) == 1:
            agent_names = [next(iter(agents_config.keys()))]
            click.echo(tr("install_agents.default_agent", agent_name=agent_names[0]))
        else:
            raise click.ClickException(tr("install_agents.agent_required"))

    selected_vms = list(vms_config.keys())
    if vm:
        if vm not in vms_config:
            raise click.ClickException(tr("install_agents.vm_missing", vm_name=vm))
        selected_vms = [vm]

    targets: List[Tuple[str, VmConfig]] = []
    for name in agent_names:
        agent = find_agent(agents_config, name)
        if all_vms:
            for vm_name in vms_config:
                targets.append((agent.name, vms_config[vm_name]))
        else:
            chosen_vm = selected_vms[0] if vm else _default_vm(agent, vms_config.keys())
            if chosen_vm not in vms_config:
                raise click.ClickException(tr("install_agents.vm_missing", vm_name=chosen_vm))
            targets.append((agent.name, vms_config[chosen_vm]))

    for target_agent_name, target_vm in targets:
        agent = find_agent(agents_config, target_agent_name)
        playbook_path = _playbook_for(agent)
        click.echo(
            tr(
                "install_agents.installing",
                agent_name=agent.name,
                agent_type=agent.type,
                vm_name=target_vm.name,
                script=playbook_path.name,
            )
        )
        try:
            _run_install_playbook(target_vm, playbook_path, proxychains=proxychains)
        except (MultipassError, ConfigError) as exc:
            raise click.ClickException(str(exc))
        click.echo(
            tr(
                "install_agents.installed",
                agent_name=agent.name,
                agent_type=agent.type,
                vm_name=target_vm.name,
            )
        )
