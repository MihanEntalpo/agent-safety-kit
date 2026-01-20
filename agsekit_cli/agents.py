from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

import click

from .config import AgentConfig, ConfigError, VmConfig, load_agents_config, load_config, load_mounts_config, load_vms_config, resolve_config_path
from .i18n import tr
from .mounts import MountConfig, normalize_path
from .vm import MultipassError, ensure_multipass_available, ensure_proxychains_runner, resolve_proxychains


NVM_LOAD_SNIPPET = (
    "export NVM_DIR=${NVM_DIR:-$HOME/.nvm}; "
    "if [ -s \"$NVM_DIR/nvm.sh\" ]; then . \"$NVM_DIR/nvm.sh\"; "
    "elif [ -s \"$NVM_DIR/bash_completion\" ]; then . \"$NVM_DIR/bash_completion\"; fi"
)
NODE_AGENT_BINARIES = {"codex", "qwen", "qwen-code"}


def load_agents_from_file(config_path: Optional[Union[str, Path]]) -> Dict[str, AgentConfig]:
    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    config = load_config(resolved_path)
    return load_agents_config(config)


def load_mounts_and_vms(config_path: Optional[Union[str, Path]]) -> Tuple[list[MountConfig], Dict[str, object]]:
    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    config = load_config(resolved_path)
    mounts = load_mounts_config(config)
    vms = load_vms_config(config)
    return mounts, vms


def find_agent(agents: Dict[str, AgentConfig], name: str) -> AgentConfig:
    try:
        return agents[name]
    except KeyError:
        raise ConfigError(tr("agents.agent_not_found", name=name))


def select_mount_for_source(
    mounts: Iterable[MountConfig],
    source_dir: Path,
    vm_name: Optional[str],
) -> Tuple[MountConfig, Path]:
    normalized = normalize_path(source_dir)
    matches: List[MountConfig] = []
    for mount in mounts:
        if normalized == mount.source:
            matches.append(mount)
            continue
        try:
            normalized.relative_to(mount.source)
        except ValueError:
            continue
        matches.append(mount)
    if vm_name:
        matches = [mount for mount in matches if mount.vm_name == vm_name]

    if not matches:
        suffix = tr("agents.mount_not_found_vm_suffix", vm_name=vm_name) if vm_name else ""
        raise ConfigError(tr("agents.mount_not_found", path=normalized, suffix=suffix))
    if len(matches) > 1:
        matches.sort(key=lambda mount: len(mount.source.parts), reverse=True)
        longest = len(matches[0].source.parts)
        if sum(1 for mount in matches if len(mount.source.parts) == longest) > 1:
            raise ConfigError(tr("agents.mount_not_found_multiple"))
    selected = matches[0]
    relative_path = normalized.relative_to(selected.source)
    return selected, relative_path


def resolve_vm(agent: AgentConfig, mount: Optional[MountConfig], vm_override: Optional[str], config: Dict[str, object]) -> str:
    if vm_override:
        return vm_override
    if mount is not None:
        return mount.vm_name
    if agent.vm_name:
        return agent.vm_name

    vms = load_vms_config(config)
    default_vm = next(iter(vms.keys())) if vms else None
    if not default_vm:
        raise ConfigError(tr("agents.vm_not_determined"))
    return default_vm


def build_agent_env(agent: AgentConfig) -> Dict[str, str]:
    return dict(agent.env)


def _export_statements(env_vars: Dict[str, str]) -> List[str]:
    exports: List[str] = []
    for key, value in env_vars.items():
        exports.append(f"export {key}={shlex.quote(str(value))}")
    return exports


def _needs_nvm(binary: str) -> bool:
    return binary in NODE_AGENT_BINARIES


def build_shell_command(workdir: Path, agent_command: Sequence[str], env_vars: Dict[str, str]) -> str:
    parts: List[str] = []
    if _needs_nvm(agent_command[0]):
        parts.append(NVM_LOAD_SNIPPET)
    exports = _export_statements(env_vars)
    if exports:
        parts.append("; ".join(exports))
    parts.append(f"cd {shlex.quote(str(workdir))}")
    parts.append(f"exec {shlex.join(list(agent_command))}")
    return " && ".join(parts)


def _debug_print(command: Union[Sequence[str], str], debug: bool) -> None:
    if not debug:
        return

    if isinstance(command, str):
        click.echo(tr("agents.debug_command", command=command))
    else:
        click.echo(tr("agents.debug_command", command=shlex.join(command)))


def run_in_vm(
    vm: VmConfig,
    workdir: Path,
    agent_command: Sequence[str],
    env_vars: Dict[str, str],
    *,
    proxychains: Optional[str] = None,
    debug: bool = False,
) -> int:
    ensure_multipass_available()
    shell_command = build_shell_command(workdir, agent_command, env_vars)
    effective_proxychains = resolve_proxychains(vm, proxychains)
    if effective_proxychains:
        runner = ensure_proxychains_runner(vm)
        wrapped_command = (
            f"bash {shlex.quote(runner)} --proxy {shlex.quote(effective_proxychains)} -- "
            f"bash -lc {shlex.quote(shell_command)}"
        )
        command = ["multipass", "exec", vm.name, "--", "bash", "-lc", wrapped_command]
    else:
        command = ["multipass", "exec", vm.name, "--", "bash", "-lc", shell_command]
    _debug_print(command, debug)
    result = subprocess.run(command, check=False)
    return int(result.returncode)


def ensure_agent_binary_available(
    agent_command: Sequence[str], vm: VmConfig, *, proxychains: Optional[str] = None, debug: bool = False
) -> None:
    ensure_multipass_available()
    binary = agent_command[0]
    effective_proxychains = resolve_proxychains(vm, proxychains)
    parts = []
    if _needs_nvm(binary):
        parts.append(NVM_LOAD_SNIPPET)
    parts.append("export PATH=\"/usr/local/bin:$HOME/.local/bin:$PATH\"")
    parts.append(f"command -v {shlex.quote(binary)} >/dev/null 2>&1")
    check_command = " && ".join(parts)
    if effective_proxychains:
        runner = ensure_proxychains_runner(vm)
        wrapped_command = (
            f"bash {shlex.quote(runner)} --proxy {shlex.quote(effective_proxychains)} -- "
            f"bash -lc {shlex.quote(check_command)}"
        )
        command = ["multipass", "exec", vm.name, "--", "bash", "-lc", wrapped_command]
    else:
        command = ["multipass", "exec", vm.name, "--", "bash", "-lc", check_command]
    _debug_print(command, debug)
    result = subprocess.run(command, check=False, capture_output=True, text=True)

    if result.returncode == 0:
        return
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode == 1 and not stdout and not stderr:
        raise MultipassError(
            tr("agents.agent_binary_missing", binary=binary, vm_name=vm.name)
        )
    raise MultipassError(
        tr(
            "agents.agent_binary_check_failed",
            binary=binary,
            vm_name=vm.name,
            stdout=stdout or "-",
            stderr=stderr or "-",
        )
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
        "--max-backups",
        str(mount.max_backups),
        "--backup-clean-method",
        mount.backup_clean_method,
    ]

    if skip_first:
        command.append("--skip-first")

    mount.backup.mkdir(parents=True, exist_ok=True)
    log_file = open(mount.backup / "backup.log", "a", buffering=1)

    _debug_print(command, debug)
    process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
    process.log_file = log_file  # type: ignore[attr-defined]
    return process


def _extract_option_name(arg: str) -> Optional[str]:
    if not arg.startswith("--"):
        return None
    trimmed = arg.strip()
    if not trimmed.startswith("--"):
        return None
    for separator in ("=", " "):
        if separator in trimmed:
            return trimmed.split(separator, 1)[0]
    return trimmed


def _collect_option_names(args: Sequence[str]) -> Set[str]:
    names: Set[str] = set()
    for arg in args:
        name = _extract_option_name(arg)
        if name:
            names.add(name)
    return names


def _merge_default_args(default_args: Sequence[str], user_args: Sequence[str]) -> List[str]:
    if not default_args:
        return list(user_args)

    user_names = _collect_option_names(user_args)
    merged: List[str] = []
    index = 0
    while index < len(default_args):
        arg = default_args[index]
        name = _extract_option_name(arg)
        if name and name in user_names:
            has_inline_value = "=" in arg or any(char.isspace() for char in arg)
            if not has_inline_value and index + 1 < len(default_args):
                next_arg = default_args[index + 1]
                if not next_arg.startswith("-"):
                    index += 2
                    continue
            index += 1
            continue
        merged.append(arg)
        index += 1
    merged.extend(user_args)
    return merged


def agent_command_sequence(
    agent: AgentConfig, extra_args: Sequence[str], *, skip_default_args: bool = False
) -> List[str]:
    if skip_default_args:
        return [agent.type, *extra_args]
    merged_args = _merge_default_args(agent.default_args, extra_args)
    return [agent.type, *merged_args]


def ensure_vm_exists(vm_name: str, known_vms: Dict[str, object]) -> None:
    if vm_name not in known_vms:
        raise ConfigError(tr("agents.vm_missing", vm_name=vm_name))
