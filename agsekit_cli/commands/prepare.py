from __future__ import annotations

import os
import shutil
import subprocess

import click


@click.command(name="prepare")
def prepare_command() -> None:
    """Install Multipass dependencies on Debian-based systems."""

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
