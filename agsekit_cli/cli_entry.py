from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import List, Optional

import click

from .i18n import tr


def resolve_agsekit_script_path() -> Optional[Path]:
    argv_path = Path(sys.argv[0])
    if argv_path.name == "agsekit" and argv_path.exists():
        return argv_path.resolve()

    resolved = shutil.which("agsekit")
    if resolved:
        return Path(resolved).resolve()

    local_script = Path(__file__).resolve().parents[1] / "agsekit"
    if local_script.exists():
        return local_script

    return None


def resolve_agsekit_bin(error_key: str) -> Path:
    resolved = resolve_agsekit_script_path()
    if resolved is not None:
        return resolved
    raise click.ClickException(tr(error_key))


def resolve_agsekit_command(error_key: str) -> List[str]:
    resolved = resolve_agsekit_script_path()
    if resolved is not None:
        return [str(resolved)]

    if sys.executable:
        return [sys.executable, "-m", "agsekit_cli.cli"]

    raise click.ClickException(tr(error_key))
