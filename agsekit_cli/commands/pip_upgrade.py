from __future__ import annotations

import os
import subprocess
import sys

import click

from ..i18n import tr


def _detect_env_path() -> str:
    env_path = os.environ.get("VIRTUAL_ENV")
    if env_path:
        return env_path
    return sys.prefix


@click.command(name="pip-upgrade", help=tr("pip_upgrade.command_help"))
def pip_upgrade_command() -> None:
    """Upgrade agsekit inside the current Python environment."""
    env_path = _detect_env_path()
    click.echo(tr("pip_upgrade.env_detected", path=env_path))

    pip_command = [sys.executable, "-m", "pip"]
    check = subprocess.run(
        [*pip_command, "show", "agsekit"],
        check=False,
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        raise click.ClickException(tr("pip_upgrade.not_installed"))

    click.echo(tr("pip_upgrade.upgrading"))
    subprocess.run([*pip_command, "install", "agsekit", "--upgrade"], check=True)
    click.echo(tr("pip_upgrade.completed"))
