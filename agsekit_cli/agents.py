from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from .agents_modules import build_agent_module, get_agent_class, get_agent_class_for_runtime_binary
from .config import (
    AgentConfig,
    ConfigError,
    HttpProxyConfig,
    HttpProxyPortPoolConfig,
    VmConfig,
    load_agents_config,
    load_config,
    load_mounts_config,
    load_vms_config,
    resolve_config_path,
)
from .debug import debug_log_command, debug_log_result
from .host_tools import multipass_command
from .i18n import tr
from .mounts import MountConfig, normalize_path
from .vm import (
    HTTP_PROXY_RUNNER_PATH,
    MultipassError,
    PROXYCHAINS_RUNNER_PATH,
    RUN_AGENT_RUNNER_PATH,
    ensure_multipass_available,
    resolve_proxychains,
)


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

    vms = load_vms_config(config)
    available_vm_names = list(vms.keys())
    configured_vms = configured_agent_vms(agent, available_vm_names)
    if configured_vms:
        return configured_vms[0]
    if not available_vm_names:
        raise ConfigError(tr("agents.vm_not_determined"))
    return available_vm_names[0]


def configured_agent_vms(agent: AgentConfig, available_vms: Iterable[str]) -> List[str]:
    available = [str(vm_name) for vm_name in available_vms]
    if not agent.vm_names:
        return available
    available_set = set(available)
    return [vm_name for vm_name in agent.vm_names if vm_name in available_set]


def build_agent_env(agent: AgentConfig) -> Dict[str, str]:
    return build_agent_module(agent).build_env()


def resolve_http_proxy(agent: AgentConfig, vm: VmConfig) -> Optional[HttpProxyConfig]:
    if agent.http_proxy_defined:
        return agent.http_proxy
    return vm.http_proxy


def build_shell_command(workdir: Path, agent_command: Sequence[str], env_vars: Dict[str, str]) -> str:
    agent_cls = get_agent_class_for_runtime_binary(agent_command[0])
    return agent_cls.build_shell_command(workdir, agent_command, env_vars)


def _http_proxy_runner_args(
    http_proxy: HttpProxyConfig,
    http_proxy_port_pool: HttpProxyPortPoolConfig,
) -> List[str]:
    if http_proxy.url is not None:
        return ["--http-proxy-url", http_proxy.url]
    if http_proxy.upstream is None:
        raise ConfigError(tr("run.http_proxy_invalid_runtime"))
    args = [
        "--http-proxy-upstream",
        http_proxy.upstream,
        "--http-proxy-pool-start",
        str(http_proxy_port_pool.start),
        "--http-proxy-pool-end",
        str(http_proxy_port_pool.end),
    ]
    if http_proxy.listen is not None:
        args.extend(["--http-proxy-listen", http_proxy.listen])
    return args


def _http_proxy_wrapped_shell_command(
    shell_command: str,
    http_proxy: HttpProxyConfig,
    http_proxy_port_pool: HttpProxyPortPoolConfig,
) -> str:
    runner_command: List[str] = ["bash", HTTP_PROXY_RUNNER_PATH]
    if http_proxy.url is not None:
        runner_command.extend(["--url", http_proxy.url])
    else:
        if http_proxy.upstream is None:
            raise ConfigError(tr("run.http_proxy_invalid_runtime"))
        runner_command.extend(["--upstream", http_proxy.upstream])
        if http_proxy.listen is not None:
            runner_command.extend(["--listen", http_proxy.listen])
        runner_command.extend(
            [
                "--pool-start",
                str(http_proxy_port_pool.start),
                "--pool-end",
                str(http_proxy_port_pool.end),
            ]
        )
    runner_command.extend(["--", "bash", "-lc", shell_command])
    return shlex.join(runner_command)


def run_in_vm(
    vm: VmConfig,
    workdir: Path,
    agent_command: Sequence[str],
    env_vars: Dict[str, str],
    *,
    http_proxy: Optional[HttpProxyConfig] = None,
    http_proxy_port_pool: Optional[HttpProxyPortPoolConfig] = None,
    proxychains: Optional[str] = None,
    debug: bool = False,
) -> int:
    ensure_multipass_available()
    agent_cls = get_agent_class_for_runtime_binary(agent_command[0])
    effective_proxychains = resolve_proxychains(vm, proxychains)

    wrapper_command: List[str] = [
        RUN_AGENT_RUNNER_PATH,
        "--workdir",
        str(workdir),
        "--binary",
        agent_command[0],
    ]
    if agent_cls.needs_nvm():
        wrapper_command.append("--load-nvm")
    for key, value in env_vars.items():
        wrapper_command.extend(["--env", f"{key}={value}"])
    if effective_proxychains:
        wrapper_command.extend(["--proxychains", effective_proxychains])
    if http_proxy is not None:
        effective_pool = http_proxy_port_pool or HttpProxyPortPoolConfig()
        wrapper_command.extend(_http_proxy_runner_args(http_proxy, effective_pool))
    wrapper_command.append("--")
    wrapper_command.extend(agent_command)

    fallback_shell_command = build_shell_command(workdir, agent_command, env_vars)
    if http_proxy is not None:
        effective_pool = http_proxy_port_pool or HttpProxyPortPoolConfig()
        fallback_shell_command = _http_proxy_wrapped_shell_command(
            fallback_shell_command,
            http_proxy,
            effective_pool,
        )
    if effective_proxychains:
        fallback_shell_command = (
            f"bash {shlex.quote(PROXYCHAINS_RUNNER_PATH)} --proxy {shlex.quote(effective_proxychains)} -- "
            f"bash -lc {shlex.quote(fallback_shell_command)}"
        )

    remote_command = (
        f"if [ -x {shlex.quote(RUN_AGENT_RUNNER_PATH)} ]; then "
        f"exec {shlex.join(wrapper_command)}; "
        f"else {fallback_shell_command}; fi"
    )
    command = [multipass_command(), "exec", vm.name, "--", "bash", "-lc", remote_command]
    debug_log_command(command, enabled=debug)
    result = subprocess.run(command, check=False)
    debug_log_result(result, enabled=debug)
    return int(result.returncode)


def ensure_agent_binary_available(
    agent_command: Sequence[str],
    vm: VmConfig,
    *,
    proxychains: Optional[str] = None,
    debug: bool = False
) -> None:
    ensure_multipass_available()
    binary = agent_command[0]
    agent_cls = get_agent_class_for_runtime_binary(binary)
    effective_proxychains = resolve_proxychains(vm, proxychains)
    check_command = agent_cls.build_binary_check_command()
    if effective_proxychains:
        wrapped_command = (
            f"bash {shlex.quote(PROXYCHAINS_RUNNER_PATH)} --proxy {shlex.quote(effective_proxychains)} -- "
            f"bash -lc {shlex.quote(check_command)}"
        )
        command = [multipass_command(), "exec", vm.name, "--", "bash", "-lc", wrapped_command]
    else:
        command = [multipass_command(), "exec", vm.name, "--", "bash", "-lc", check_command]
    debug_log_command(command, enabled=debug)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    debug_log_result(result, enabled=debug)

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

    env = os.environ.copy()
    if skip_first:
        env["AGSEKIT_BACKUP_LOCK_QUIET"] = "1"

    debug_log_command(command, enabled=debug)
    process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT, env=env)
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
    runtime_binary = get_agent_class(agent.type).runtime_binary
    if skip_default_args:
        return [runtime_binary, *extra_args]
    merged_args = _merge_default_args(agent.default_args, extra_args)
    return [runtime_binary, *merged_args]


def ensure_vm_exists(vm_name: str, known_vms: Dict[str, object]) -> None:
    if vm_name not in known_vms:
        raise ConfigError(tr("agents.vm_missing", vm_name=vm_name))
