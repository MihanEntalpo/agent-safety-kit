from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import click

from ..debug import debug_scope
from ..i18n import tr
from ..progress import ProgressManager
from ..vm_prepare import ensure_host_ssh_keypair
from . import debug_option, non_interactive_option
from ..config import load_global_config_from_path


DEBIAN_MULTIPASS_PACKAGES = [
    "snapd",
    "qemu-kvm",
    "libvirt-daemon-system",
    "libvirt-clients",
    "bridge-utils",
]
DEBIAN_SSH_PACKAGES = ["openssh-client"]
DEBIAN_RSYNC_PACKAGES = ["rsync"]
ARCH_SSH_PACKAGES = ["openssh"]
ARCH_RSYNC_PACKAGES = ["rsync"]


def _is_wsl() -> bool:
    if platform.system() != "Linux":
        return False

    release_paths = [Path("/proc/sys/kernel/osrelease"), Path("/proc/version")]
    for release_path in release_paths:
        try:
            value = release_path.read_text(encoding="utf-8").lower()
        except OSError:
            continue
        if "microsoft" in value or "wsl" in value:
            return True

    release = platform.release().lower()
    return "microsoft" in release or "wsl" in release


def _debian_package_installed(package: str) -> bool:
    if shutil.which("dpkg-query") is None:
        return False
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", package],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "install ok installed" in result.stdout


def _arch_package_installed(package: str) -> bool:
    if shutil.which("pacman") is None:
        return False
    result = subprocess.run(
        ["pacman", "-Q", package],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _install_debian_packages_if_missing(packages: list[str], *, quiet: bool = False) -> None:
    missing = [package for package in packages if not _debian_package_installed(package)]
    if not missing:
        if not quiet:
            click.echo(tr("prepare.host_packages_already_installed"))
        return

    if not quiet:
        click.echo(tr("prepare.installing_host_packages", packages=", ".join(missing)))

    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    subprocess.run(["sudo", "apt-get", "update"], check=True, env=env)
    subprocess.run(["sudo", "apt-get", "install", "-y"] + missing, check=True, env=env)


def _install_arch_packages_if_missing(packages: list[str], *, quiet: bool = False) -> None:
    missing = [package for package in packages if not _arch_package_installed(package)]
    if not missing:
        if not quiet:
            click.echo(tr("prepare.host_packages_already_installed"))
        return

    if not quiet:
        click.echo(tr("prepare.installing_host_packages", packages=", ".join(missing)))

    subprocess.run(["sudo", "pacman", "-S", "--needed", "--noconfirm"] + missing, check=True)


def _ensure_ssh_keygen(*, quiet: bool = False) -> None:
    if shutil.which("ssh-keygen") is not None:
        return

    if shutil.which("pacman") is not None:
        _install_arch_packages_if_missing(ARCH_SSH_PACKAGES, quiet=quiet)
    elif shutil.which("apt-get") is not None:
        _install_debian_packages_if_missing(DEBIAN_SSH_PACKAGES, quiet=quiet)
    else:
        raise click.ClickException(tr("prepare.ssh_keygen_missing"))

    if shutil.which("ssh-keygen") is None:
        raise click.ClickException(tr("prepare.ssh_keygen_missing"))


def _ensure_rsync(*, quiet: bool = False) -> None:
    if shutil.which("rsync") is not None:
        return

    if platform.system() == "Darwin":
        if shutil.which("brew") is None:
            raise click.ClickException(tr("prepare.rsync_missing"))
        if not quiet:
            click.echo(tr("prepare.installing_rsync_brew"))
        subprocess.run(["brew", "install", "rsync"], check=True)
    elif shutil.which("pacman") is not None:
        _install_arch_packages_if_missing(ARCH_RSYNC_PACKAGES, quiet=quiet)
    elif shutil.which("apt-get") is not None:
        _install_debian_packages_if_missing(DEBIAN_RSYNC_PACKAGES, quiet=quiet)
    else:
        raise click.ClickException(tr("prepare.rsync_missing"))

    if shutil.which("rsync") is None:
        raise click.ClickException(tr("prepare.rsync_missing"))


def _install_multipass(*, quiet: bool = False) -> None:
    if shutil.which("multipass") is not None:
        if not quiet:
            click.echo(tr("prepare.multipass_already_installed"))
        return

    if _is_wsl():
        raise click.ClickException(tr("prepare.wsl_multipass_missing"))

    if not quiet:
        click.echo(tr("prepare.installing_dependencies"))

    if shutil.which("pacman") is not None:
        _install_multipass_arch(quiet=quiet)
    elif shutil.which("apt-get") is not None:
        _install_multipass_debian(quiet=quiet)
    elif platform.system() == "Darwin" and shutil.which("brew") is not None:
        _install_multipass_brew(quiet=quiet)
    else:
        raise click.ClickException(tr("prepare.apt_missing"))


def _install_multipass_debian(*, quiet: bool = False) -> None:
    """Install Multipass on Debian-based systems via snap."""
    _install_debian_packages_if_missing(DEBIAN_MULTIPASS_PACKAGES, quiet=quiet)

    if shutil.which("snap") is None:
        raise click.ClickException(tr("prepare.snap_missing"))

    subprocess.run(["sudo", "snap", "install", "multipass", "--classic"], check=True)
    if not quiet:
        click.echo(tr("prepare.multipass_installed"))


def _install_multipass_arch(*, quiet: bool = False) -> None:
    """Install Multipass on Arch Linux via an AUR helper."""
    if not quiet:
        click.echo(tr("prepare.installing_multipass_arch"))

    if shutil.which("yay") is not None:
        aur_helper = "yay"
    elif shutil.which("aura") is not None:
        aur_helper = "aura"
    else:
        raise click.ClickException(tr("prepare.aur_helper_missing"))

    subprocess.run(
        [aur_helper, "-S", "--noconfirm", "multipass", "libvirt", "dnsmasq", "qemu-base"],
        check=True,
    )
    if not quiet:
        click.echo(tr("prepare.multipass_installed_arch"))


def _install_multipass_brew(*, quiet: bool = False) -> None:
    """Install Multipass on macOS via Homebrew."""
    if not quiet:
        click.echo(tr("prepare.installing_multipass_brew"))

    subprocess.run(["brew", "install", "multipass"], check=True)
    if not quiet:
        click.echo(tr("prepare.multipass_installed_brew"))


def _prepare_host_dependencies(*, quiet: bool = False) -> None:
    _install_multipass(quiet=quiet)
    _ensure_ssh_keygen(quiet=quiet)
    _ensure_rsync(quiet=quiet)


def run_prepare(*, debug: bool, config_path: Optional[str] = None, progress: Optional[ProgressManager] = None) -> None:
    task_id = None

    def _update(description: str) -> None:
        if progress and task_id is not None:
            progress.update(task_id, description=description)

    def _advance() -> None:
        if progress and task_id is not None:
            progress.advance(task_id)

    global_config = load_global_config_from_path(
        Path(config_path) if config_path else None,
        allow_missing=True,
    )

    with debug_scope(debug):
        _update(tr("progress.up_prepare_multipass"))
        if progress and hasattr(progress, "suspend"):
            with progress.suspend():
                _prepare_host_dependencies(quiet=True)
        else:
            _prepare_host_dependencies(quiet=progress is not None)
        _advance()

        _update(tr("progress.up_prepare_ssh"))
        if not progress:
            click.echo(tr("prepare.ensure_keypair"))
        ensure_host_ssh_keypair(ssh_dir=global_config.ssh_keys_folder, verbose=debug)
        _advance()


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
@debug_option
def prepare_command(non_interactive: bool, config_path: Optional[str], debug: bool) -> None:
    """Install Multipass dependencies on supported hosts and prepare VMs."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive
    run_prepare(debug=debug, config_path=config_path)
