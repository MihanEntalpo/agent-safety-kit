from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

import click

from ..i18n import tr
from ..vm_prepare import ensure_host_ssh_keypair
from . import non_interactive_option


def _install_multipass() -> None:
    if shutil.which("multipass") is not None:
        click.echo(tr("prepare.multipass_already_installed"))
        return

    click.echo(tr("prepare.installing_dependencies"))

    if shutil.which("apt-get") is None:
        raise click.ClickException(tr("prepare.apt_missing"))

    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}

    subprocess.run(["sudo", "apt-get", "update"], check=True, env=env)
    subprocess.run(
        ["sudo", "apt-get", "install", "-y", "snapd", "qemu-kvm", "libvirt-daemon-system", "libvirt-clients", "bridge-utils"],
        check=True,
        env=env,
    )

    if shutil.which("snap") is None:
        raise click.ClickException(tr("prepare.snap_missing"))

    subprocess.run(["sudo", "snap", "install", "multipass", "--classic"], check=True)
    click.echo(tr("prepare.multipass_installed"))


@click.command(name="prepare", help=tr("prepare.command_help"))
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def prepare_command(non_interactive: bool, config_path: Optional[str]) -> None:
    """Install Multipass dependencies on Debian-based systems and prepare VMs."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive
    del config_path

    _install_multipass()
    click.echo(tr("prepare.ensure_keypair"))
    ensure_host_ssh_keypair()
