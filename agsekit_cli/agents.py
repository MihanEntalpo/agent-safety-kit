from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import click

from .config import AgentConfig, ConfigError, load_agents_config, load_config, load_mounts_config, load_vms_config, resolve_config_path
from .mounts import MountConfig, normalize_path
from .vm import MultipassError, ensure_multipass_available


NVM_LOAD_SNIPPET = (
    "export NVM_DIR=${NVM_DIR:-$HOME/.nvm}; "
    "if [ -s \"$NVM_DIR/nvm.sh\" ]; then . \"$NVM_DIR/nvm.sh\"; "
    "elif [ -s \"$NVM_DIR/bash_completion\" ]; then . \"$NVM_DIR/bash_completion\"; fi"
)


def load_agents_from_file(config_path: str | Path | None) -> Dict[str, AgentConfig]:
    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    config = load_config(resolved_path)
    return load_agents_config(config)


def load_mounts_and_vms(config_path: str | Path | None) -> Tuple[list[MountConfig], Dict[str, object]]:
    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    config = load_config(resolved_path)
    mounts = load_mounts_config(config)
    vms = load_vms_config(config)
    return mounts, vms


def find_agent(agents: Dict[str, AgentConfig], name: str) -> AgentConfig:
    try:
        return agents[name]
    except KeyError:
        raise ConfigError(f"Агент `{name}` не найден в конфигурации")


def select_mount_for_source(mounts: Iterable[MountConfig], source_dir: Path, vm_name: str | None) -> MountConfig:
    normalized = normalize_path(source_dir)
    matches = [mount for mount in mounts if mount.source == normalized]
    if vm_name:
        matches = [mount for mount in matches if mount.vm_name == vm_name]

    if not matches:
        suffix = f" для ВМ {vm_name}" if vm_name else ""
        raise ConfigError(f"Монтирование с путем {normalized} не найдено{suffix}")
    if len(matches) > 1:
        raise ConfigError("Найдено несколько монтирований с таким путем. Уточните ВМ через --vm.")
    return matches[0]


def resolve_vm(agent: AgentConfig, mount: MountConfig | None, vm_override: str | None, config: Dict[str, object]) -> str:
    if vm_override:
        return vm_override
    if mount is not None:
        return mount.vm_name
    if agent.vm_name:
        return agent.vm_name

    vms = load_vms_config(config)
    default_vm = next(iter(vms.keys())) if vms else None
    if not default_vm:
        raise ConfigError("Не удалось определить ВМ для запуска агента")
    return default_vm


def build_agent_env(agent: AgentConfig) -> Dict[str, str]:
    env_vars = dict(agent.env)
    if agent.socks5_proxy:
        proxy = f"socks5://{agent.socks5_proxy}"
        if agent.type == "qwen" and not proxy.startswith(("http://", "https://")):
            return env_vars
        env_vars.setdefault("ALL_PROXY", proxy)
        env_vars.setdefault("HTTPS_PROXY", proxy)
        env_vars.setdefault("HTTP_PROXY", proxy)
    return env_vars


def _export_statements(env_vars: Dict[str, str]) -> List[str]:
    exports: List[str] = []
    for key, value in env_vars.items():
        exports.append(f"export {key}={shlex.quote(str(value))}")
    return exports


def build_shell_command(workdir: Path, agent_command: Sequence[str], env_vars: Dict[str, str]) -> str:
    parts: List[str] = [NVM_LOAD_SNIPPET]
    exports = _export_statements(env_vars)
    if exports:
        parts.append("; ".join(exports))
    parts.append(f"cd {shlex.quote(str(workdir))}")
    parts.append(shlex.join(list(agent_command)))
    return " && ".join(parts)


def _debug_print(command: Sequence[str] | str, debug: bool) -> None:
    if not debug:
        return

    if isinstance(command, str):
        click.echo(f"[DEBUG] {command}")
    else:
        click.echo(f"[DEBUG] {shlex.join(command)}")


def run_in_vm(
    vm_name: str,
    workdir: Path,
    agent_command: Sequence[str],
    env_vars: Dict[str, str],
    *,
    debug: bool = False,
) -> int:
    ensure_multipass_available()
    shell_command = build_shell_command(workdir, agent_command, env_vars)
    command = [
        "multipass",
        "exec",
        vm_name,
        "--",
        "bash",
        "-lc",
        shell_command,
    ]
    _debug_print(command, debug)
    result = subprocess.run(command, check=False)
    return int(result.returncode)


def ensure_agent_binary_available(
    agent_command: Sequence[str], vm_name: str, *, debug: bool = False
) -> None:
    ensure_multipass_available()
    binary = agent_command[0]
    command = [
        "multipass",
        "exec",
        vm_name,
        "--",
        "bash",
        "-lc",
        f"{NVM_LOAD_SNIPPET} && command -v {shlex.quote(binary)} >/dev/null 2>&1",
    ]
    _debug_print(command, debug)
    result = subprocess.run(command, check=False, capture_output=True, text=True)

    if result.returncode != 0:
        raise MultipassError(
            f"Agent binary `{binary}` was not found inside VM `{vm_name}`. Did you run ./agsekit install-agents?"
        )


def start_backup_process(
    mount: MountConfig, cli_path: Path, *, skip_first: bool = False, debug: bool = False
) -> subprocess.Popen[bytes]:
    command = [
        str(cli_path),
        "backup-repeated",
        "--source-dir",
        str(mount.source),
        "--dest-dir",
        str(mount.backup),
        "--interval",
        str(mount.interval_minutes),
    ]

    if skip_first:
        command.append("--skip-first")

    mount.backup.mkdir(parents=True, exist_ok=True)
    log_file = open(mount.backup / "backup.log", "a", buffering=1)

    _debug_print(command, debug)
    process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
    process.log_file = log_file  # type: ignore[attr-defined]
    return process


def agent_command_sequence(agent: AgentConfig, extra_args: Sequence[str]) -> List[str]:
    return [agent.type, *extra_args]


def ensure_vm_exists(vm_name: str, known_vms: Dict[str, object]) -> None:
    if vm_name not in known_vms:
        raise ConfigError(f"ВМ `{vm_name}` отсутствует в конфигурации")
