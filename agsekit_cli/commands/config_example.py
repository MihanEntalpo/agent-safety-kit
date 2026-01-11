from __future__ import annotations

import shutil
import sysconfig
from pathlib import Path
from typing import Optional

import click

from ..config import DEFAULT_CONFIG_PATH
from ..i18n import tr


def _find_example_source() -> Optional[Path]:
    data_path = Path(sysconfig.get_paths()["data"]) / "share" / "agsekit" / "config-example.yaml"
    repo_path = Path(__file__).resolve().parents[2] / "config-example.yaml"
    for candidate in (data_path, repo_path):
        if candidate.exists():
            return candidate
    return None


@click.command(name="config-example", help=tr("config_example.command_help"))
@click.argument("destination", required=False)
def config_example_command(destination: Optional[str]) -> None:
    source_path = _find_example_source()
    if source_path is None:
        raise click.ClickException(tr("config_example.source_missing"))

    if destination:
        target_path = Path(destination).expanduser()
        if target_path.exists():
            raise click.ClickException(tr("config_example.destination_exists", path=target_path))
    else:
        target_path = DEFAULT_CONFIG_PATH
        if target_path.exists():
            click.echo(tr("config_example.destination_exists_skip", path=target_path))
            return

    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, target_path)
    click.echo(tr("config_example.copied", path=target_path))
