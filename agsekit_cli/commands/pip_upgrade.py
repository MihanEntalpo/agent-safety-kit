from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

import click

from ..i18n import tr


def _detect_env_path() -> str:
    env_path = os.environ.get("VIRTUAL_ENV")
    if env_path:
        return env_path
    return sys.prefix


def _extract_version_from_pip_show(output: str) -> Optional[str]:
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith("version:"):
            version = line.split(":", 1)[1].strip()
            return version or None
    return None


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

    old_version = _extract_version_from_pip_show(check.stdout or "") or tr("pip_upgrade.version_unknown")

    click.echo(tr("pip_upgrade.upgrading"))
    subprocess.run([*pip_command, "install", "agsekit", "--upgrade"], check=True)

    check_after = subprocess.run(
        [*pip_command, "show", "agsekit"],
        check=False,
        capture_output=True,
        text=True,
    )
    new_version = _extract_version_from_pip_show(check_after.stdout or "") or tr("pip_upgrade.version_unknown")

    if old_version == new_version:
        click.echo(tr("pip_upgrade.already_latest", version=new_version))
    else:
        click.echo(tr("pip_upgrade.completed_with_versions", old=old_version, new=new_version))
