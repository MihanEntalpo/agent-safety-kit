from __future__ import annotations

import subprocess
import sys

import click

from .i18n import tr


class AnsibleCollectionError(RuntimeError):
    """Raised when required ansible collection cannot be installed."""


def _ansible_galaxy_command() -> list[str]:
    return [sys.executable, "-m", "ansible.cli.galaxy"]


def ensure_multipass_collection() -> None:
    galaxy_command = _ansible_galaxy_command()
    try:
        list_result = subprocess.run(
            [*galaxy_command, "collection", "list", "theko2fi.multipass"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise AnsibleCollectionError(
            tr("prepare.ansible_galaxy_missing", python=sys.executable)
        ) from exc

    if list_result.returncode == 0 and "theko2fi.multipass" in (list_result.stdout or ""):
        return

    click.echo(tr("prepare.installing_ansible_collection"))
    try:
        install_result = subprocess.run(
            [*galaxy_command, "collection", "install", "theko2fi.multipass"],
            check=False,
            capture_output=False,
            text=True,
        )
    except FileNotFoundError as exc:
        raise AnsibleCollectionError(
            tr("prepare.ansible_galaxy_missing", python=sys.executable)
        ) from exc

    if install_result.returncode != 0:
        raise AnsibleCollectionError(tr("prepare.installing_ansible_collection_failed"))
