from __future__ import annotations

import subprocess

import click

from .i18n import tr


class AnsibleCollectionError(RuntimeError):
    """Raised when required ansible collection cannot be installed."""


def ensure_multipass_collection() -> None:
    list_result = subprocess.run(
        ["ansible-galaxy", "collection", "list", "theko2fi.multipass"],
        check=False,
        capture_output=True,
        text=True,
    )
    if list_result.returncode == 0 and "theko2fi.multipass" in (list_result.stdout or ""):
        return

    click.echo(tr("prepare.installing_ansible_collection"))
    install_result = subprocess.run(
        ["ansible-galaxy", "collection", "install", "theko2fi.multipass"],
        check=False,
        capture_output=False,
        text=True,
    )
    if install_result.returncode != 0:
        raise AnsibleCollectionError(tr("prepare.installing_ansible_collection_failed"))
