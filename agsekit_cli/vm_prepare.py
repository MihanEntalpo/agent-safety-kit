from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import click

from .i18n import tr
from .vm_bundles import resolve_bundles
from .vm import MultipassError


def _run_multipass(command: list[str], description: str, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    click.echo(tr("prepare.command_running", description=description, command=" ".join(shlex.quote(part) for part in command)))
    return subprocess.run(command, check=False, capture_output=capture_output, text=True)


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
    check_result = _run_multipass(
        ["multipass", "exec", vm_name, "--", "bash", "-lc", "dpkg -s git proxychains4 ripgrep >/dev/null 2>&1"],
        tr("prepare.checking_packages", vm_name=vm_name),
    )
    if check_result.returncode == 0:
        click.echo(tr("prepare.packages_already_installed", vm_name=vm_name))
        return

    click.echo(tr("prepare.installing_packages", vm_name=vm_name))
    install_command = [
        "multipass",
        "exec",
        vm_name,
        "--",
        "bash",
        "-lc",
        "sudo DEBIAN_FRONTEND=noninteractive apt-get update && "
        "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y git proxychains4 ripgrep",
    ]
    result = _run_multipass(install_command, tr("prepare.installing_packages", vm_name=vm_name), capture_output=False)
    if result.returncode != 0:
        raise MultipassError(tr("prepare.install_failed", vm_name=vm_name))


def _install_vm_bundles(vm_name: str, bundles: List[str]) -> None:
    if not bundles:
        click.echo(tr("prepare.install_bundles_none", vm_name=vm_name))
        return

    resolved = resolve_bundles(bundles, vm_name)
    bundle_list = ", ".join(bundle.raw for bundle in resolved)
    click.echo(tr("prepare.install_bundles_start", vm_name=vm_name, bundles=bundle_list))

    for bundle in resolved:
        click.echo(tr("prepare.install_bundle_running", vm_name=vm_name, bundle=bundle.raw))
        remote_path = f"/tmp/agsekit_bundle_{bundle.name}.sh"
        transfer_command = ["multipass", "transfer", str(bundle.script), f"{vm_name}:{remote_path}"]
        transfer_result = _run_multipass(
            transfer_command,
            tr("prepare.install_bundle_transfer", vm_name=vm_name, bundle=bundle.raw),
        )
        if transfer_result.returncode != 0:
            raise MultipassError(tr("prepare.install_bundle_copy_failed", vm_name=vm_name, bundle=bundle.raw))

        install_command = ["multipass", "exec", vm_name, "--", "bash", remote_path]
        if bundle.version:
            install_command.append(bundle.version)
        install_result = _run_multipass(
            install_command,
            tr("prepare.install_bundle_exec", vm_name=vm_name, bundle=bundle.raw),
            capture_output=False,
        )
        if install_result.returncode != 0:
            raise MultipassError(tr("prepare.install_bundle_failed", vm_name=vm_name, bundle=bundle.raw))

        cleanup_command = ["multipass", "exec", vm_name, "--", "rm", "-f", remote_path]
        cleanup_result = _run_multipass(
            cleanup_command,
            tr("prepare.install_bundle_cleanup", vm_name=vm_name, bundle=bundle.raw),
        )
        if cleanup_result.returncode != 0:
            click.echo(tr("prepare.install_bundle_cleanup_failed", vm_name=vm_name, bundle=bundle.raw), err=True)


def _ensure_vm_keypair(vm_name: str, public_key: Path) -> None:
    click.echo(tr("prepare.syncing_keys", vm_name=vm_name))
    prep_command = [
        "multipass",
        "exec",
        vm_name,
        "--",
        "bash",
        "-lc",
        "sudo install -d -m 700 -o ubuntu -g ubuntu /home/ubuntu/.ssh",
    ]
    prep_result = _run_multipass(prep_command, tr("prepare.ensure_ssh_dir", vm_name=vm_name))
    if prep_result.returncode != 0:
        raise MultipassError(tr("prepare.ensure_ssh_dir_failed", vm_name=vm_name))

    desired_public = public_key.read_text(encoding="utf-8")

    public_key_line = desired_public.strip()
    click.echo(tr("prepare.ensure_authorized_keys", vm_name=vm_name))
    authorized_command = [
        "multipass",
        "exec",
        vm_name,
        "--",
        "bash",
        "-lc",
        "sudo touch /home/ubuntu/.ssh/authorized_keys && "
        "sudo chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys && "
        "sudo chmod 600 /home/ubuntu/.ssh/authorized_keys && "
        f"grep -Fqx {shlex.quote(public_key_line)} /home/ubuntu/.ssh/authorized_keys || "
        f"echo {shlex.quote(public_key_line)} | sudo tee -a /home/ubuntu/.ssh/authorized_keys >/dev/null",
    ]
    authorized_result = _run_multipass(authorized_command, tr("prepare.ensure_authorized_keys_command", vm_name=vm_name))
    if authorized_result.returncode != 0:
        raise MultipassError(tr("prepare.authorized_keys_failed", vm_name=vm_name))


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


def _ensure_known_host(host: str) -> None:
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    known_hosts = ssh_dir / "known_hosts"

    if known_hosts.exists():
        check = subprocess.run(
            ["ssh-keygen", "-F", host, "-f", str(known_hosts)],
            check=False,
            capture_output=True,
            text=True,
        )
        if check.returncode == 0:
            return

    scan = subprocess.run(
        ["ssh-keyscan", "-H", host],
        check=False,
        capture_output=True,
        text=True,
    )
    if scan.returncode != 0 or not scan.stdout.strip():
        raise MultipassError(tr("prepare.known_hosts_failed", host=host))

    with known_hosts.open("a", encoding="utf-8") as handle:
        handle.write(scan.stdout)
    os.chmod(known_hosts, 0o644)


def prepare_vm(vm_name: str, public_key: Path, bundles: Optional[List[str]] = None) -> None:
    click.echo(tr("prepare.preparing_vm", vm_name=vm_name))
    _run_multipass(["multipass", "start", vm_name], tr("prepare.starting_vm", vm_name=vm_name))
    _ensure_vm_packages(vm_name)
    _install_vm_bundles(vm_name, bundles or [])
    _ensure_vm_keypair(vm_name, public_key)
    click.echo(tr("prepare.ensure_known_hosts", vm_name=vm_name))
    for host in _fetch_vm_ips(vm_name):
        _ensure_known_host(host)
    click.echo(tr("prepare.prepared_vm", vm_name=vm_name))
