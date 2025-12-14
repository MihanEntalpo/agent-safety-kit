from __future__ import annotations

import subprocess
from pathlib import Path
import subprocess
from pathlib import Path
from typing import Iterable, List

import click

from ..agents import find_agent
from ..config import AgentConfig, ConfigError, load_agents_config, load_config, load_vms_config, resolve_config_path
from ..vm import MultipassError, ensure_multipass_available

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "agent_scripts"


def _script_for(agent: AgentConfig) -> Path:
    candidate = SCRIPTS_DIR / f"{agent.type}.sh"
    if not candidate.exists():
        raise ConfigError(f"Скрипт установки для типа {agent.type} не найден: {candidate}")
    return candidate


def _run_install_script(vm_name: str, script_path: Path) -> None:
    ensure_multipass_available()
    with script_path.open("rb") as handle:
        result = subprocess.run(
            ["multipass", "exec", vm_name, "--", "bash", "-s"],
            check=False,
            stdin=handle,
        )
    if result.returncode != 0:
        raise MultipassError(f"Установка агента во ВМ {vm_name} завершилась с ошибкой {result.returncode}")


def _default_vm(agent: AgentConfig, available: Iterable[str]) -> str:
    if agent.vm_name:
        return agent.vm_name
    try:
        return next(iter(available))
    except StopIteration:
        raise ConfigError("В конфигурации нет доступных ВМ для установки агента")


@click.command(name="setup-agents")
@click.argument("agent_name", required=False)
@click.argument("vm", required=False)
@click.option("--all-vms", is_flag=True, help="Установить агента во все ВМ из конфигурации")
@click.option("--all-agents", is_flag=True, help="Установить всех агентов из конфигурации")
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию config.yaml или $CONFIG_PATH).",
)
def setup_agents_command(agent_name: str | None, vm: str | None, all_vms: bool, all_agents: bool, config_path: str | None) -> None:
    """Устанавливает агентов в указанные ВМ Multipass."""

    if all_agents and agent_name:
        raise click.ClickException("Нельзя одновременно указывать имя агента и --all-agents.")

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        agents_config = load_agents_config(config)
        vms_config = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if not agents_config:
        raise click.ClickException("В конфигурации не описаны агенты.")

    agent_names: List[str]
    if all_agents:
        agent_names = list(agents_config.keys())
    else:
        if not agent_name:
            raise click.ClickException("Укажите имя агента или используйте флаг --all-agents.")
        agent_names = [agent_name]

    selected_vms = list(vms_config.keys())
    if vm:
        if vm not in vms_config:
            raise click.ClickException(f"ВМ `{vm}` не найдена в конфигурации")
        selected_vms = [vm]

    targets: List[tuple[str, str | None]] = []
    for name in agent_names:
        agent = find_agent(agents_config, name)
        if all_vms:
            for vm_name in vms_config:
                targets.append((agent.name, vm_name))
        else:
            chosen_vm = selected_vms[0] if vm else _default_vm(agent, vms_config.keys())
            if chosen_vm not in vms_config:
                raise click.ClickException(f"ВМ `{chosen_vm}` не найдена в конфигурации")
            targets.append((agent.name, chosen_vm))

    for target_agent_name, target_vm in targets:
        agent = find_agent(agents_config, target_agent_name)
        script_path = _script_for(agent)
        try:
            _run_install_script(target_vm, script_path)
        except (MultipassError, ConfigError) as exc:
            raise click.ClickException(str(exc))
        click.echo(f"Агент {agent.name} ({agent.type}) установлен в ВМ {target_vm} с помощью {script_path.name}.")
