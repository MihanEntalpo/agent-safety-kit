from __future__ import annotations

import os
import platform
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


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _build_windows_upgrade_reexec_code(old_version: str) -> str:
    already_latest_template = tr("pip_upgrade.already_latest", version="{version}")
    completed_template = tr("pip_upgrade.completed_with_versions", old="{old}", new="{new}")

    return f"""
import subprocess
import sys


def extract_version(output):
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith("version:"):
            version = line.split(":", 1)[1].strip()
            return version or None
    return None


pip_command = [sys.executable, "-m", "pip"]
old_version = {old_version!r}
version_unknown = {tr("pip_upgrade.version_unknown")!r}
already_latest_template = {already_latest_template!r}
completed_template = {completed_template!r}

print({tr("pip_upgrade.upgrading")!r})
subprocess.run([*pip_command, "install", "agsekit", "--upgrade"], check=True)

check_after = subprocess.run(
    [*pip_command, "show", "agsekit"],
    check=False,
    capture_output=True,
    text=True,
)
new_version = extract_version(check_after.stdout or "") or version_unknown

if old_version == new_version:
    print(already_latest_template.format(version=new_version))
else:
    print(completed_template.format(old=old_version, new=new_version))
"""


def _exec_windows_pip_upgrade(old_version: str) -> None:
    code = _build_windows_upgrade_reexec_code(old_version)
    os.execv(sys.executable, [sys.executable, "-c", code])
    raise RuntimeError("os.execv returned unexpectedly")


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

    if _is_windows():
        _exec_windows_pip_upgrade(old_version)

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
