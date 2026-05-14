from __future__ import annotations

import click

from ..i18n import tr
from ..versioning import find_pyproject_version, installed_version


@click.command(name="version", help=tr("version.command_help"))
def version_command() -> None:
    installed = installed_version()
    project = find_pyproject_version()

    if not installed and not project:
        raise click.ClickException(tr("version.unavailable"))

    if installed:
        click.echo(tr("version.installed", version=installed))
    if project:
        click.echo(tr("version.project", version=project))
