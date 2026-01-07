from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

import click

from ..config import DEFAULT_CONFIG_PATH, resolve_config_path
from . import non_interactive_option

ENV_FILENAME = "systemd.env"
UNIT_RELATIVE_PATH = Path("systemd") / "agsekit-portforward.service"


def _resolve_agsekit_bin() -> Path:
    resolved = shutil.which("agsekit")
    if resolved:
        return Path(resolved).resolve()

    local_script = Path(__file__).resolve().parents[2] / "agsekit"
    if local_script.exists():
        return local_script

    raise click.ClickException("Не удалось найти исполняемый файл agsekit.")


def _format_command(command: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _run_systemctl(command: List[str]) -> None:
    click.echo(f"Выполняется: {_format_command(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Не удалось выполнить systemctl."
        raise click.ClickException(message)
    if result.stdout:
        click.echo(result.stdout.rstrip())
    if result.stderr:
        click.echo(result.stderr.rstrip(), err=True)


@click.group(name="systemd")
def systemd_group() -> None:
    """Команды для управления systemd-юнитами."""


@systemd_group.command(name="install")
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Путь к YAML-конфигурации (по умолчанию ~/.config/agsekit/config.yaml или $CONFIG_PATH).",
)
def systemd_install_command(config_path: Optional[str], non_interactive: bool) -> None:
    """Генерирует systemd.env и регистрирует unit для portforward."""
    del non_interactive

    project_dir = Path.cwd().resolve()
    agsekit_bin = _resolve_agsekit_bin()
    resolved_config = resolve_config_path(Path(config_path) if config_path else None).resolve()

    env_dir = DEFAULT_CONFIG_PATH.parent
    env_dir.mkdir(parents=True, exist_ok=True)
    env_path = env_dir / ENV_FILENAME

    env_contents = (
        f"AGSEKIT_BIN={agsekit_bin}\n"
        f"AGSEKIT_CONFIG={resolved_config}\n"
        f"AGSEKIT_PROJECT_DIR={project_dir}\n"
    )
    env_path.write_text(env_contents, encoding="utf-8")
    click.echo(f"Записан файл окружения: {env_path}")

    unit_path = project_dir / UNIT_RELATIVE_PATH
    if not unit_path.exists():
        raise click.ClickException(f"Файл systemd-юнита не найден: {unit_path}")

    _run_systemctl(["systemctl", "--user", "link", str(unit_path)])
    _run_systemctl(["systemctl", "--user", "daemon-reload"])
    _run_systemctl(["systemctl", "--user", "start", "agsekit-portforward"])
    _run_systemctl(["systemctl", "--user", "enable", "agsekit-portforward"])


@systemd_group.command(name="uninstall")
@non_interactive_option
def systemd_uninstall_command(non_interactive: bool) -> None:
    """Останавливает и удаляет systemd-юнит для portforward."""
    del non_interactive

    project_dir = Path.cwd().resolve()
    unit_path = project_dir / UNIT_RELATIVE_PATH
    if not unit_path.exists():
        raise click.ClickException(f"Файл systemd-юнита не найден: {unit_path}")

    _run_systemctl(["systemctl", "--user", "stop", "agsekit-portforward"])
    _run_systemctl(["systemctl", "--user", "disable", "agsekit-portforward"])
    _run_systemctl(["systemctl", "--user", "unlink", str(unit_path)])
    _run_systemctl(["systemctl", "--user", "daemon-reload"])
