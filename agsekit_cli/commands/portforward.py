from __future__ import annotations

import shlex
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

import click

from ..config import ConfigError, load_config, load_vms_config, resolve_config_path
from ..i18n import tr
from ..vm import MultipassError, build_port_forwarding_args, ensure_multipass_available
from . import non_interactive_option


def _resolve_agsekit_command() -> List[str]:
    resolved = shutil.which("agsekit")
    if resolved:
        return [resolved]

    local_script = Path(__file__).resolve().parents[2] / "agsekit"
    if local_script.exists():
        return [str(local_script)]

    raise click.ClickException(tr("portforward.cli_not_found"))


def _format_command(command: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _start_forwarder(
    base_command: List[str],
    vm_name: str,
    config_path: Path,
    port_args: List[str],
) -> subprocess.Popen:
    command = [
        *base_command,
        "ssh",
        "--config",
        str(config_path),
        vm_name,
        "-N",
        "-o",
        "ExitOnForwardFailure=yes",
        *port_args,
    ]
    click.echo(tr("portforward.starting", vm_name=vm_name, command=_format_command(command)))
    return subprocess.Popen(command)


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
def portforward_command(config_path: Optional[str], non_interactive: bool) -> None:
    """Запускает ssh-туннели по правилам port-forwarding из конфигурации."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    try:
        ensure_multipass_available()
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    base_command = _resolve_agsekit_command()
    forward_targets: Dict[str, List[str]] = {}
    for vm_name, vm in vms.items():
        port_args = build_port_forwarding_args(vm.port_forwarding)
        if port_args:
            forward_targets[vm_name] = port_args

    if not forward_targets:
        click.echo(tr("portforward.rules_missing"))
        return

    processes: Dict[str, subprocess.Popen] = {}
    stop_requested = False

    def _handle_signal(signum: int, frame: object) -> None:
        nonlocal stop_requested
        if not stop_requested:
            click.echo(tr("portforward.stop_requested"))
        stop_requested = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    for vm_name, port_args in forward_targets.items():
        processes[vm_name] = _start_forwarder(base_command, vm_name, resolved_path, port_args)

    try:
        while not stop_requested:
            for vm_name, proc in list(processes.items()):
                return_code = proc.poll()
                if return_code is None:
                    continue
                if stop_requested:
                    break
                click.echo(tr("portforward.process_restarting", vm_name=vm_name, code=return_code))
                processes[vm_name] = _start_forwarder(base_command, vm_name, resolved_path, forward_targets[vm_name])
            time.sleep(1)
    finally:
        _terminate_processes(processes)
