from __future__ import annotations

import os
import shutil
import subprocess

import click


@click.command(name="prepare")
def prepare_command() -> None:
    """Устанавливает зависимости multipass в deb-based системах."""

    if shutil.which("apt-get") is None:
        raise click.ClickException("Поддерживаются только deb-based системы с apt.")

    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}

    subprocess.run(["sudo", "apt-get", "update"], check=True, env=env)
    subprocess.run(
        ["sudo", "apt-get", "install", "-y", "snapd", "qemu-kvm", "libvirt-daemon-system", "libvirt-clients", "bridge-utils"],
        check=True,
        env=env,
    )

    if shutil.which("snap") is None:
        raise click.ClickException("snap недоступен после установки snapd. Проверьте установку и повторите попытку.")

    subprocess.run(["sudo", "snap", "install", "multipass", "--classic"], check=True)
    click.echo("Multipass установлен.")
