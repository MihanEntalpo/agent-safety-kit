from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import click

from .ansible_utils import AnsibleCollectionError, ensure_multipass_collection
from .debug import debug_log_command, debug_log_result
from .i18n import tr
from .vm_bundles import resolve_bundles
from .vm import MultipassError


def _run_multipass(command: list[str], description: str, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    click.echo(tr("prepare.command_running", description=description, command=" ".join(shlex.quote(part) for part in command)))
    debug_log_command(command)
    result = subprocess.run(command, check=False, capture_output=capture_output, text=True)
    debug_log_result(result)
    return result


def ensure_host_ssh_keypair() -> Tuple[Path, Path]:
    ssh_dir = Path.home() / ".config" / "agsekit" / "ssh"
    private_key = ssh_dir / "id_rsa"
    public_key = ssh_dir / "id_rsa.pub"
    ssh_dir.mkdir(parents=True, exist_ok=True)

    if private_key.exists() and public_key.exists():
        click.echo(tr("prepare.ssh_keypair_exists", path=ssh_dir))
        return private_key, public_key

    if private_key.exists() and not public_key.exists():
        click.echo(tr("prepare.ssh_public_missing", path=ssh_dir))
        result = subprocess.run(
            ["ssh-keygen", "-y", "-f", str(private_key)],
            check=True,
            capture_output=True,
            text=True,
        )
        public_key.write_text(result.stdout, encoding="utf-8")
    else:
        click.echo(tr("prepare.ssh_generating", path=ssh_dir))
        subprocess.run(
            ["ssh-keygen", "-t", "rsa", "-b", "4096", "-N", "", "-f", str(private_key)],
            check=True,
        )

    os.chmod(private_key, 0o600)
    if public_key.exists():
        os.chmod(public_key, 0o644)

    click.echo(tr("prepare.ssh_ready", path=ssh_dir))
    return private_key, public_key


def _ensure_vm_packages(vm_name: str) -> None:
    click.echo(tr("prepare.installing_packages", vm_name=vm_name))
    playbook = Path(__file__).resolve().parent / "ansible" / "vm_packages.yml"
    command = [
        "ansible-playbook",
        "-i",
        "localhost,",
        "-e",
        f"vm_name={vm_name}",
        str(playbook),
    ]
    result = subprocess.run(command, check=False, capture_output=False, text=True)
    if result.returncode != 0:
        raise MultipassError(tr("prepare.install_failed", vm_name=vm_name))


def _ensure_vm_ssh_access(vm_name: str, public_key: Path, vm_known_hosts: Iterable[str]) -> None:
    click.echo(tr("prepare.syncing_keys", vm_name=vm_name))
    click.echo(tr("prepare.ensure_authorized_keys", vm_name=vm_name))
    click.echo(tr("prepare.ensure_known_hosts", vm_name=vm_name))

    playbook = Path(__file__).resolve().parent / "ansible" / "vm_ssh.yml"
    public_key_line = public_key.read_text(encoding="utf-8").strip()
    known_hosts = [host.strip() for host in vm_known_hosts if host and host.strip()]
    extra_vars = {
        "vm_name": vm_name,
        "host_public_key": public_key_line,
        "vm_known_hosts": known_hosts,
    }
    command = [
        "ansible-playbook",
        "-i",
        "localhost,",
        "-e",
        json.dumps(extra_vars, ensure_ascii=False),
        str(playbook),
    ]
    result = subprocess.run(command, check=False, capture_output=False, text=True)
    if result.returncode != 0:
        raise MultipassError(tr("prepare.ssh_sync_failed", vm_name=vm_name))


def _install_vm_bundles(vm_name: str, bundles: List[str]) -> None:
    if not bundles:
        click.echo(tr("prepare.install_bundles_none", vm_name=vm_name))
        return

    resolved = resolve_bundles(bundles, vm_name)
    bundle_list = ", ".join(bundle.raw for bundle in resolved)
    click.echo(tr("prepare.install_bundles_start", vm_name=vm_name, bundles=bundle_list))

    for bundle in resolved:
        click.echo(tr("prepare.install_bundle_running", vm_name=vm_name, bundle=bundle.raw))
        playbook = bundle.playbook
        command = [
            "ansible-playbook",
            "-i",
            "localhost,",
            "-e",
            f"vm_name={vm_name}",
        ]
        if bundle.version:
            command.extend(["-e", f"bundle_version={bundle.version}"])
        command.append(str(playbook))
        click.echo(tr("prepare.install_bundle_exec", vm_name=vm_name, bundle=bundle.raw))
        install_result = subprocess.run(command, check=False, capture_output=False, text=True)
        if install_result.returncode != 0:
            raise MultipassError(tr("prepare.install_bundle_failed", vm_name=vm_name, bundle=bundle.raw))


def _fetch_vm_ips(vm_name: str) -> List[str]:
    result = _run_multipass(
        ["multipass", "info", vm_name, "--format", "json"],
        tr("prepare.fetching_vm_info", vm_name=vm_name),
    )
    if result.returncode != 0:
        raise MultipassError(tr("prepare.vm_info_failed", vm_name=vm_name))

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MultipassError(tr("prepare.vm_info_parse_failed", vm_name=vm_name)) from exc

    info = data.get("info", {}) if isinstance(data, dict) else {}
    vm_info = info.get(vm_name, {}) if isinstance(info, dict) else {}
    ipv4 = vm_info.get("ipv4") or vm_info.get("IPv4") or []
    if isinstance(ipv4, str):
        return [ipv4] if ipv4 else []
    if isinstance(ipv4, list):
        return [item for item in ipv4 if isinstance(item, str) and item]
    return []


def prepare_vm(vm_name: str, public_key: Path, bundles: Optional[List[str]] = None) -> None:
    click.echo(tr("prepare.preparing_vm", vm_name=vm_name))
    try:
        ensure_multipass_collection()
    except AnsibleCollectionError as exc:
        raise MultipassError(str(exc))
    _run_multipass(["multipass", "start", vm_name], tr("prepare.starting_vm", vm_name=vm_name))
    hosts = _fetch_vm_ips(vm_name)
    if not hosts:
        raise MultipassError(tr("prepare.no_vm_ips", vm_name=vm_name))
    _ensure_vm_ssh_access(vm_name, public_key, [vm_name, *hosts])
    _ensure_vm_packages(vm_name)
    _install_vm_bundles(vm_name, bundles or [])
    click.echo(tr("prepare.prepared_vm", vm_name=vm_name))
