from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Sequence

import click

from ..config import ConfigError, load_config, load_vms_config, resolve_config_path
from ..vm import MultipassError, ensure_multipass_available
from . import non_interactive_option


def _resolve_ssh_key() -> Path:
    key_path = Path.home() / ".config" / "agsekit" / "ssh" / "id_rsa"
    if not key_path.exists():
        raise click.ClickException(
            f"SSH ключ не найден по пути {key_path}. Запустите `agsekit prepare`, чтобы создать и синхронизировать ключи."
        )
    return key_path


def _fetch_vm_ip(vm_name: str) -> str:
    result = subprocess.run(
        ["multipass", "info", vm_name, "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise MultipassError(result.stderr.strip() or f"Не удалось получить информацию о ВМ {vm_name}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MultipassError(f"Не удалось разобрать вывод multipass info для {vm_name}: {exc}")

    info = data.get("info", {}).get(vm_name, {})
    ipv4 = info.get("ipv4")
    if isinstance(ipv4, list):
        ip_value = ipv4[0] if ipv4 else ""
    elif isinstance(ipv4, str):
        ip_value = ipv4
    else:
        ip_value = ""

    if not ip_value:
        raise MultipassError(f"Multipass не вернул IPv4 адрес для ВМ {vm_name}")
    return ip_value


@click.command(name="ssh", context_settings={"ignore_unknown_options": True})
@non_interactive_option
@click.argument("vm_name", required=True)
@click.argument("ssh_args", nargs=-1, type=click.UNPROCESSED)
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию ~/.config/agsekit/config.yaml или $CONFIG_PATH).",
)
def ssh_command(
    vm_name: str,
    ssh_args: Sequence[str],
    config_path: Optional[str],
    non_interactive: bool,
) -> None:
    """Подключается к ВМ по SSH с передачей дополнительных аргументов."""

    if shutil.which("ssh") is None:
        raise click.ClickException("Не удалось найти ssh. Установите OpenSSH client.")

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if vm_name not in vms:
        raise click.ClickException(f"ВМ `{vm_name}` отсутствует в конфигурации")

    try:
        ensure_multipass_available()
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    key_path = _resolve_ssh_key()
    try:
        ip_address = _fetch_vm_ip(vm_name)
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    ssh_args_list = list(ssh_args)
    if "--" in ssh_args_list:
        delimiter_index = ssh_args_list.index("--")
        ssh_options = ssh_args_list[:delimiter_index]
        ssh_command_args = ssh_args_list[delimiter_index + 1 :]
        command = [
            "ssh",
            "-i",
            str(key_path),
            *ssh_options,
            f"ubuntu@{ip_address}",
            "--",
            *ssh_command_args,
        ]
    else:
        command = ["ssh", "-i", str(key_path), *ssh_args_list, f"ubuntu@{ip_address}"]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
