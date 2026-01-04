from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Iterable, List, Optional

import click

from ..agents import find_agent
from ..config import AgentConfig, ConfigError, VmConfig, load_agents_config, load_config, load_vms_config, resolve_config_path
from ..vm import MultipassError, build_port_forwarding_args, ensure_multipass_available, resolve_proxychains, wrap_with_proxychains
from . import non_interactive_option

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "agent_scripts"


def _script_for(agent: AgentConfig) -> Path:
    candidate = SCRIPTS_DIR / f"{agent.type}.sh"
    if not candidate.exists():
        raise ConfigError(f"Installation script for type {agent.type} is missing: {candidate}")
    return candidate


def _run_install_script(vm: VmConfig, script_path: Path, proxychains: Optional[str] = None) -> None:
    ensure_multipass_available()
    effective_proxychains = resolve_proxychains(vm, proxychains)
    remote_path = f"/tmp/agsekit-{script_path.stem}-{uuid.uuid4().hex}.sh"
    transfer_result = subprocess.run(
        wrap_with_proxychains(["multipass", "transfer", str(script_path), f"{vm.name}:{remote_path}"], effective_proxychains),
        check=False,
    )
    if transfer_result.returncode != 0:
        raise MultipassError(f"Failed to copy installer {script_path.name} to VM {vm.name}.")

    try:
        result = subprocess.run(
            wrap_with_proxychains(
                ["multipass", "ssh", vm.name, *build_port_forwarding_args(vm.port_forwarding), "--", "bash", remote_path],
                effective_proxychains,
            ),
            check=False,
        )
        if result.returncode != 0:
            raise MultipassError(f"Agent installation in VM {vm.name} failed with exit code {result.returncode}.")
    finally:
        subprocess.run(
            wrap_with_proxychains(
                ["multipass", "ssh", vm.name, *build_port_forwarding_args(vm.port_forwarding), "--", "rm", "-f", remote_path],
                effective_proxychains,
            ),
            check=False,
        )


def _default_vm(agent: AgentConfig, available: Iterable[str]) -> str:
    if agent.vm_name:
        return agent.vm_name
    try:
        return next(iter(available))
    except StopIteration:
        raise ConfigError("No VMs are available in the configuration for agent installation")


@click.command(name="install-agents")
@non_interactive_option
@click.argument("agent_name", required=False)
@click.argument("vm", required=False)
@click.option("--all-vms", is_flag=True, help="Install the agent into every VM from the configuration")
@click.option("--all-agents", is_flag=True, help="Install every agent from the configuration")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Path to the YAML config (defaults to ~/.config/agsekit/config.yaml or $CONFIG_PATH).",
)
@click.option(
    "--proxychains",
    default=None,
    show_default=False,
    help="Override the proxy URL from the config for this run (scheme://host:port); use an empty string to disable.",
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

    click.echo("Preparing agent installation targets...")

    if all_agents and agent_name:
        raise click.ClickException("Specify either an agent name or --all-agents, not both.")

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        agents_config = load_agents_config(config)
        vms_config = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if not agents_config:
        raise click.ClickException("No agents are defined in the configuration.")

    agent_names: List[str]
    if all_agents:
        agent_names = list(agents_config.keys())
    else:
        if agent_name:
            agent_names = [agent_name]
        elif len(agents_config) == 1:
            agent_names = [next(iter(agents_config.keys()))]
            click.echo(f"Agent name not provided: using the only configured agent `{agent_names[0]}`.")
        else:
            raise click.ClickException("Provide an agent name or use --all-agents.")

    selected_vms = list(vms_config.keys())
    if vm:
        if vm not in vms_config:
            raise click.ClickException(f"VM `{vm}` is not defined in the configuration")
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
                raise click.ClickException(f"VM `{chosen_vm}` is not defined in the configuration")
            targets.append((agent.name, vms_config[chosen_vm]))

    for target_agent_name, target_vm in targets:
        agent = find_agent(agents_config, target_agent_name)
        script_path = _script_for(agent)
        click.echo(f"Installing {agent.name} ({agent.type}) into VM {target_vm.name} using {script_path.name}...")
        try:
            _run_install_script(target_vm, script_path, proxychains=proxychains)
        except (MultipassError, ConfigError) as exc:
            raise click.ClickException(str(exc))
        click.echo(f"Agent {agent.name} ({agent.type}) installed into VM {target_vm.name}.")
