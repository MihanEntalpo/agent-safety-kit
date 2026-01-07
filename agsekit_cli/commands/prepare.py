from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

import click

from ..config import ConfigError, VmConfig, load_config, load_vms_config, resolve_config_path
from ..vm import MultipassError, ensure_multipass_available, fetch_existing_info
from . import non_interactive_option


def _install_multipass() -> None:
    if shutil.which("multipass") is not None:
        click.echo("Multipass is already installed, skipping preparation steps.")
        return

    click.echo("Installing required packages for Multipass...")

    if shutil.which("apt-get") is None:
        raise click.ClickException("Only Debian-based systems with apt are supported.")

    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}

    subprocess.run(["sudo", "apt-get", "update"], check=True, env=env)
    subprocess.run(
        ["sudo", "apt-get", "install", "-y", "snapd", "qemu-kvm", "libvirt-daemon-system", "libvirt-clients", "bridge-utils"],
        check=True,
        env=env,
    )

    if shutil.which("snap") is None:
        raise click.ClickException("snap is unavailable after installing snapd. Please check the installation and retry.")

    subprocess.run(["sudo", "snap", "install", "multipass", "--classic"], check=True)
    click.echo("Multipass installation completed.")


def _ensure_host_ssh_keypair() -> Tuple[Path, Path]:
    ssh_dir = Path.home() / ".config" / "agsekit" / "ssh"
    private_key = ssh_dir / "id_rsa"
    public_key = ssh_dir / "id_rsa.pub"
    ssh_dir.mkdir(parents=True, exist_ok=True)

    if private_key.exists() and public_key.exists():
        click.echo(f"SSH keypair already exists at {ssh_dir}, reusing.")
        return private_key, public_key

    if private_key.exists() and not public_key.exists():
        click.echo(f"Public key missing in {ssh_dir}, generating from existing private key.")
        result = subprocess.run(
            ["ssh-keygen", "-y", "-f", str(private_key)],
            check=True,
            capture_output=True,
            text=True,
        )
        public_key.write_text(result.stdout, encoding="utf-8")
    else:
        click.echo(f"Generating new SSH keypair in {ssh_dir}.")
        subprocess.run(
            ["ssh-keygen", "-t", "rsa", "-b", "4096", "-N", "", "-f", str(private_key)],
            check=True,
        )

    os.chmod(private_key, 0o600)
    if public_key.exists():
        os.chmod(public_key, 0o644)

    click.echo(f"SSH keypair is ready at {ssh_dir}.")
    return private_key, public_key


def _run_multipass(command: list[str], description: str, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    click.echo(f"{description}: {' '.join(shlex.quote(part) for part in command)}")
    return subprocess.run(command, check=False, capture_output=capture_output, text=True)


def _ensure_vm_packages(vm_name: str) -> None:
    check_result = _run_multipass(
        ["multipass", "exec", vm_name, "--", "bash", "-lc", "dpkg -s git proxychains4 >/dev/null 2>&1"],
        f"Checking packages in {vm_name}",
    )
    if check_result.returncode == 0:
        click.echo(f"Packages git and proxychains4 are already installed in {vm_name}.")
        return

    click.echo(f"Installing git and proxychains4 in {vm_name}.")
    install_command = [
        "multipass",
        "exec",
        vm_name,
        "--",
        "bash",
        "-lc",
        "sudo DEBIAN_FRONTEND=noninteractive apt-get update && "
        "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y git proxychains4",
    ]
    result = _run_multipass(install_command, f"Installing git and proxychains4 in {vm_name}", capture_output=False)
    if result.returncode != 0:
        raise MultipassError(f"Failed to install git/proxychains4 in VM {vm_name}.")


def _read_vm_file(vm_name: str, path: str) -> Optional[str]:
    result = _run_multipass(
        ["multipass", "exec", vm_name, "--", "bash", "-lc", f"sudo cat {shlex.quote(path)}"],
        f"Reading {path} from {vm_name}",
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _ensure_vm_keypair(vm_name: str, private_key: Path, public_key: Path) -> None:
    click.echo(f"Syncing SSH keys into {vm_name} for user ubuntu.")
    prep_command = [
        "multipass",
        "exec",
        vm_name,
        "--",
        "bash",
        "-lc",
        "sudo install -d -m 700 -o ubuntu -g ubuntu /home/ubuntu/.ssh",
    ]
    prep_result = _run_multipass(prep_command, f"Ensuring /home/ubuntu/.ssh in {vm_name}")
    if prep_result.returncode != 0:
        raise MultipassError(f"Failed to prepare /home/ubuntu/.ssh in VM {vm_name}.")

    desired_private = private_key.read_text(encoding="utf-8")
    desired_public = public_key.read_text(encoding="utf-8")

    current_private = _read_vm_file(vm_name, "/home/ubuntu/.ssh/id_rsa")
    if current_private != desired_private:
        click.echo(f"Updating private key in {vm_name}.")
        transfer_result = _run_multipass(
            ["multipass", "transfer", str(private_key), f"{vm_name}:/home/ubuntu/.ssh/id_rsa"],
            f"Transferring private key to {vm_name}",
        )
        if transfer_result.returncode != 0:
            raise MultipassError(f"Failed to transfer private key to VM {vm_name}.")

    current_public = _read_vm_file(vm_name, "/home/ubuntu/.ssh/id_rsa.pub")
    if current_public != desired_public:
        click.echo(f"Updating public key in {vm_name}.")
        transfer_result = _run_multipass(
            ["multipass", "transfer", str(public_key), f"{vm_name}:/home/ubuntu/.ssh/id_rsa.pub"],
            f"Transferring public key to {vm_name}",
        )
        if transfer_result.returncode != 0:
            raise MultipassError(f"Failed to transfer public key to VM {vm_name}.")

    permissions_command = [
        "multipass",
        "exec",
        vm_name,
        "--",
        "bash",
        "-lc",
        "sudo chown ubuntu:ubuntu /home/ubuntu/.ssh/id_rsa /home/ubuntu/.ssh/id_rsa.pub && "
        "sudo chmod 600 /home/ubuntu/.ssh/id_rsa && sudo chmod 644 /home/ubuntu/.ssh/id_rsa.pub",
    ]
    permissions_result = _run_multipass(permissions_command, f"Setting key permissions in {vm_name}")
    if permissions_result.returncode != 0:
        raise MultipassError(f"Failed to set key permissions in VM {vm_name}.")

    public_key_line = desired_public.strip()
    click.echo(f"Ensuring authorized_keys for ubuntu in {vm_name}.")
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
    authorized_result = _run_multipass(authorized_command, f"Ensuring authorized_keys in {vm_name}")
    if authorized_result.returncode != 0:
        raise MultipassError(f"Failed to update authorized_keys in VM {vm_name}.")


def _existing_vm_names() -> set[str]:
    raw_info = fetch_existing_info()
    try:
        data = json.loads(raw_info)
    except json.JSONDecodeError:
        return set()
    return {item.get("name") for item in data.get("list", []) if item.get("name")}


def _prepare_vms(config_path: Optional[str]) -> None:
    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    if not resolved_path.exists():
        click.echo(f"Config file not found at {resolved_path}, skipping VM preparation.")
        return

    click.echo(f"Loading VM configuration from {resolved_path}.")
    try:
        config = load_config(resolved_path)
        vms_config: Dict[str, VmConfig] = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    ensure_multipass_available()
    existing_vms = _existing_vm_names()
    if not existing_vms:
        click.echo("No Multipass VMs found, skipping VM preparation.")
        return

    click.echo("Ensuring SSH keypair for VM access.")
    private_key, public_key = _ensure_host_ssh_keypair()

    for vm in vms_config.values():
        if vm.name not in existing_vms:
            click.echo(f"VM {vm.name} is not created yet, skipping.")
            continue

        click.echo(f"Preparing VM {vm.name}...")
        _run_multipass(["multipass", "start", vm.name], f"Starting VM {vm.name}")
        _ensure_vm_packages(vm.name)
        _ensure_vm_keypair(vm.name, private_key, public_key)
        click.echo(f"VM {vm.name} is prepared.")


@click.command(name="prepare")
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Path to the YAML config (defaults to ~/.config/agsekit/config.yaml or $CONFIG_PATH).",
)
def prepare_command(non_interactive: bool, config_path: Optional[str]) -> None:
    """Install Multipass dependencies on Debian-based systems and prepare VMs."""

    _install_multipass()
    _prepare_vms(config_path)
