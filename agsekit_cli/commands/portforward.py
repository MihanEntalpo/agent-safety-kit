from __future__ import annotations

from dataclasses import dataclass
import shlex
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import click

from .. import cli_entry
from ..config import (
    ConfigError,
    PortForwardingRule,
    VmConfig,
    load_config,
    load_global_config,
    load_vms_config,
    resolve_config_path,
)
from ..i18n import tr
from ..vm import MultipassError, build_port_forwarding_args, ensure_multipass_available
from . import debug_option, non_interactive_option

@dataclass(frozen=True)
class ForwarderTarget:
    port_args: tuple[str, ...]
    privileged_remote_ports: tuple[int, ...]


@dataclass(frozen=True)
class PortforwardRuntimeConfig:
    targets: Dict[str, ForwarderTarget]
    check_interval_sec: int


def _resolve_agsekit_command() -> List[str]:
    return cli_entry.resolve_agsekit_command("portforward.cli_not_found")


def _format_command(command: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _find_privileged_remote_ports(rules: Sequence[PortForwardingRule]) -> List[int]:
    ports: List[int] = []
    for rule in rules:
        if rule.type != "remote":
            continue
        try:
            port = int(rule.vm_addr.rsplit(":", 1)[-1])
        except ValueError:
            continue
        if 0 < port < 1024:
            ports.append(port)
    return sorted(set(ports))


def _start_forwarder(
    base_command: List[str],
    vm_name: str,
    config_path: Path,
    port_args: List[str],
    *,
    debug: bool = False,
) -> subprocess.Popen:
    command = [
        *base_command,
        "ssh",
    ]
    if debug:
        command.append("--debug")
    command.extend(
        [
            "--config",
            str(config_path),
            vm_name,
            "-N",
            "-o",
            "ExitOnForwardFailure=yes",
            *port_args,
        ]
    )
    click.echo(tr("portforward.starting", vm_name=vm_name, command=_format_command(command)))
    return subprocess.Popen(command)


def _terminate_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if proc.poll() is None:
            proc.kill()


def _terminate_processes(processes: Dict[str, subprocess.Popen]) -> None:
    for proc in processes.values():
        if proc.poll() is None:
            proc.terminate()

    deadline = time.monotonic() + 5
    for proc in processes.values():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            break

    for proc in processes.values():
        if proc.poll() is None:
            proc.kill()


def _collect_forward_targets(vms: Dict[str, VmConfig]) -> Dict[str, ForwarderTarget]:
    targets: Dict[str, ForwarderTarget] = {}
    for vm_name, vm in vms.items():
        port_args = tuple(build_port_forwarding_args(vm.port_forwarding))
        if not port_args:
            continue
        targets[vm_name] = ForwarderTarget(
            port_args=port_args,
            privileged_remote_ports=tuple(_find_privileged_remote_ports(vm.port_forwarding)),
        )
    return targets


def _load_portforward_runtime(config_path: Path) -> PortforwardRuntimeConfig:
    config = load_config(config_path)
    global_config = load_global_config(config)
    vms = load_vms_config(config)
    return PortforwardRuntimeConfig(
        targets=_collect_forward_targets(vms),
        check_interval_sec=global_config.portforward_config_check_interval_sec,
    )


def _stop_forwarder(vm_name: str, processes: Dict[str, subprocess.Popen]) -> None:
    proc = processes.pop(vm_name, None)
    if proc is None:
        return
    click.echo(tr("portforward.stopping", vm_name=vm_name))
    _terminate_process(proc)


def _reconcile_forwarders(
    processes: Dict[str, subprocess.Popen],
    current_targets: Dict[str, ForwarderTarget],
    desired_targets: Dict[str, ForwarderTarget],
    base_command: List[str],
    config_path: Path,
    *,
    debug: bool = False,
) -> None:
    current_vm_names = set(current_targets)
    desired_vm_names = set(desired_targets)

    for vm_name in sorted(current_vm_names - desired_vm_names):
        _stop_forwarder(vm_name, processes)

    for vm_name in sorted(current_vm_names & desired_vm_names):
        if current_targets[vm_name] == desired_targets[vm_name]:
            continue
        click.echo(tr("portforward.reconfiguring", vm_name=vm_name))
        _stop_forwarder(vm_name, processes)
        processes[vm_name] = _start_forwarder(
            base_command,
            vm_name,
            config_path,
            list(desired_targets[vm_name].port_args),
            debug=debug,
        )

    for vm_name in sorted(desired_vm_names - current_vm_names):
        processes[vm_name] = _start_forwarder(
            base_command,
            vm_name,
            config_path,
            list(desired_targets[vm_name].port_args),
            debug=debug,
        )


def _maybe_reload_forward_targets(
    config_path: Path,
    current_targets: Dict[str, ForwarderTarget],
    current_check_interval_sec: int,
    processes: Dict[str, subprocess.Popen],
    base_command: List[str],
    *,
    debug: bool = False,
    last_warning: Optional[str] = None,
) -> tuple[Dict[str, ForwarderTarget], int, Optional[str]]:
    try:
        desired_runtime = _load_portforward_runtime(config_path)
    except ConfigError as exc:
        warning = tr("portforward.config_reload_failed", path=config_path, error=str(exc))
        if warning != last_warning:
            click.echo(warning, err=True)
        return current_targets, current_check_interval_sec, warning

    if last_warning is not None:
        click.echo(tr("portforward.config_reload_recovered", path=config_path))

    desired_targets = desired_runtime.targets
    if desired_targets == current_targets:
        return current_targets, desired_runtime.check_interval_sec, None

    click.echo(tr("portforward.config_changed", path=config_path))
    _reconcile_forwarders(
        processes,
        current_targets,
        desired_targets,
        base_command,
        config_path,
        debug=debug,
    )
    if not desired_targets:
        click.echo(tr("portforward.rules_missing_waiting"))
    return desired_targets, desired_runtime.check_interval_sec, None


@click.command(name="portforward", help=tr("portforward.command_help"))
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
@debug_option
def portforward_command(config_path: Optional[str], debug: bool, non_interactive: bool) -> None:
    """Запускает ssh-туннели по правилам port-forwarding из конфигурации."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        runtime_config = _load_portforward_runtime(resolved_path)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    try:
        ensure_multipass_available()
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    base_command = _resolve_agsekit_command()
    forward_targets = runtime_config.targets
    check_interval_sec = runtime_config.check_interval_sec
    processes: Dict[str, subprocess.Popen] = {}
    stop_requested = False
    last_reload_warning: Optional[str] = None

    def _handle_signal(signum: int, frame: object) -> None:
        nonlocal stop_requested
        if not stop_requested:
            click.echo(tr("portforward.stop_requested"))
        stop_requested = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not forward_targets:
        click.echo(tr("portforward.rules_missing_waiting"))
    else:
        for vm_name, target in forward_targets.items():
            processes[vm_name] = _start_forwarder(
                base_command, vm_name, resolved_path, list(target.port_args), debug=debug
            )

    next_reload_at = time.monotonic() + check_interval_sec

    try:
        while not stop_requested:
            now = time.monotonic()
            if now >= next_reload_at:
                forward_targets, check_interval_sec, last_reload_warning = _maybe_reload_forward_targets(
                    resolved_path,
                    forward_targets,
                    check_interval_sec,
                    processes,
                    base_command,
                    debug=debug,
                    last_warning=last_reload_warning,
                )
                next_reload_at = now + check_interval_sec

            for vm_name, proc in list(processes.items()):
                return_code = proc.poll()
                if return_code is None:
                    continue
                if stop_requested:
                    break
                click.echo(tr("portforward.process_restarting", vm_name=vm_name, code=return_code))
                target = forward_targets.get(vm_name)
                if target is None:
                    continue
                if target.privileged_remote_ports:
                    click.echo(
                        tr(
                            "portforward.privileged_port_hint",
                            vm_name=vm_name,
                            ports=", ".join(str(port) for port in target.privileged_remote_ports),
                        )
                    )
                processes[vm_name] = _start_forwarder(
                    base_command, vm_name, resolved_path, list(target.port_args), debug=debug
                )
            time.sleep(1)
    finally:
        _terminate_processes(processes)
