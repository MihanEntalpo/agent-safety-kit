from __future__ import annotations

import json
import signal
import subprocess
from pathlib import Path
from typing import Optional, Sequence

import click

from ..config import ConfigError, load_config, load_global_config, load_vms_config, resolve_config_path
from ..debug import debug_log_command, debug_log_result, debug_scope
from ..host_tools import host_tool_exists, multipass_command, ssh_command as resolved_ssh_command
from ..i18n import tr
from ..vm import MultipassError, ensure_multipass_available
from . import debug_option, non_interactive_option


def _resolve_ssh_key(ssh_keys_folder: Path) -> Path:
    key_path = ssh_keys_folder / "id_rsa"
    if not key_path.exists():
        raise click.ClickException(
            tr("ssh.key_missing", path=key_path)
        )
    return key_path


def _fetch_vm_ip(vm_name: str, *, debug: bool = False) -> str:
    command = [multipass_command(), "info", vm_name, "--format", "json"]
    debug_log_command(command, enabled=debug)
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    debug_log_result(result, enabled=debug)
    if result.returncode != 0:
        raise MultipassError(result.stderr.strip() or tr("ssh.info_failed", vm_name=vm_name))

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MultipassError(tr("ssh.info_parse_failed", vm_name=vm_name, error=exc))

    info = data.get("info", {}).get(vm_name, {})
    ipv4 = info.get("ipv4")
    if isinstance(ipv4, list):
        ip_value = ipv4[0] if ipv4 else ""
    elif isinstance(ipv4, str):
        ip_value = ipv4
    else:
        ip_value = ""

    if not ip_value:
        raise MultipassError(tr("ssh.ip_missing", vm_name=vm_name))
    return ip_value


def _run_ssh_process(command: list[str], *, debug: bool = False) -> int:
    process = subprocess.Popen(command)
    previous_handlers = {}

    def _forward_signal(signum: int, frame: object) -> None:
        del frame
        if process.poll() is None:
            process.send_signal(signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, _forward_signal)

    try:
        return_code = process.wait()
    finally:
        for signum, previous_handler in previous_handlers.items():
            signal.signal(signum, previous_handler)

    debug_log_result(subprocess.CompletedProcess(command, return_code), enabled=debug)
    return return_code


@click.command(name="ssh", context_settings={"ignore_unknown_options": True}, help=tr("ssh.command_help"))
@non_interactive_option
@click.argument("vm_name", required=True)
@click.argument("ssh_args", nargs=-1, type=click.UNPROCESSED)
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
@debug_option
def ssh_command(
    vm_name: str,
    ssh_args: Sequence[str],
    config_path: Optional[str],
    debug: bool,
    non_interactive: bool,
) -> None:
    """Подключается к ВМ по SSH с передачей дополнительных аргументов."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    if not host_tool_exists("ssh"):
        raise click.ClickException(tr("ssh.client_missing"))

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        global_config = load_global_config(config)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if vm_name not in vms:
        raise click.ClickException(tr("ssh.vm_missing", vm_name=vm_name))

    with debug_scope(debug):
        try:
            ensure_multipass_available()
        except MultipassError as exc:
            raise click.ClickException(str(exc))

        key_path = _resolve_ssh_key(global_config.ssh_keys_folder)
        try:
            ip_address = _fetch_vm_ip(vm_name, debug=debug)
        except MultipassError as exc:
            raise click.ClickException(str(exc))

        ssh_args_list = list(ssh_args)
        if "--" in ssh_args_list:
            delimiter_index = ssh_args_list.index("--")
            ssh_options = ssh_args_list[:delimiter_index]
            ssh_command_args = ssh_args_list[delimiter_index + 1 :]
            command = [
                resolved_ssh_command(),
                "-i",
                str(key_path),
                *ssh_options,
                f"ubuntu@{ip_address}",
                "--",
                *ssh_command_args,
            ]
        else:
            command = [resolved_ssh_command(), "-i", str(key_path), *ssh_args_list, f"ubuntu@{ip_address}"]
        debug_log_command(command, enabled=debug)
        return_code = _run_ssh_process(command, debug=debug)
        if return_code != 0:
            raise SystemExit(return_code)
