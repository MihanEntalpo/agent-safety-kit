from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

import click

from ..config import DEFAULT_CONFIG_PATH, resolve_config_path
from ..i18n import tr
from . import non_interactive_option

ENV_FILENAME = "systemd.env"
UNIT_RELATIVE_PATH = Path("systemd") / "agsekit-portforward.service"
SERVICE_NAME = "agsekit-portforward"
LINKED_UNIT_PATH = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"


def _resolve_agsekit_bin() -> Path:
    resolved = shutil.which("agsekit")
    if resolved:
        return Path(resolved).resolve()

    local_script = Path(__file__).resolve().parents[2] / "agsekit"
    if local_script.exists():
        return local_script

    raise click.ClickException(tr("systemd.cli_not_found"))


def _format_command(command: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _run_systemctl(command: List[str], *, announce: bool = True) -> None:
    if announce:
        click.echo(tr("systemd.running_command", command=_format_command(command)))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or tr("systemd.systemctl_failed")
        raise click.ClickException(message)
    if announce and result.stdout:
        click.echo(result.stdout.rstrip())
    if announce and result.stderr:
        click.echo(result.stderr.rstrip(), err=True)


def write_systemd_env(config_path: Optional[Path], *, project_dir: Optional[Path] = None, announce: bool = True) -> Path:
    resolved_project_dir = (project_dir or Path.cwd()).resolve()
    agsekit_bin = _resolve_agsekit_bin()
    resolved_config = resolve_config_path(config_path).resolve()

    env_dir = DEFAULT_CONFIG_PATH.parent
    env_dir.mkdir(parents=True, exist_ok=True)
    env_path = env_dir / ENV_FILENAME

    env_contents = (
        f"AGSEKIT_BIN={agsekit_bin}\n"
        f"AGSEKIT_CONFIG={resolved_config}\n"
        f"AGSEKIT_PROJECT_DIR={resolved_project_dir}\n"
    )
    env_path.write_text(env_contents, encoding="utf-8")
    if announce:
        click.echo(tr("systemd.env_written", path=env_path))
    return env_path


def _same_link_target(link_path: Path, target_path: Path) -> bool:
    if not link_path.exists():
        return False
    try:
        return link_path.resolve() == target_path.resolve()
    except OSError:
        return False


def _ensure_current_unit_link(unit_path: Path, *, announce: bool) -> None:
    if _same_link_target(LINKED_UNIT_PATH, unit_path):
        return

    try:
        if LINKED_UNIT_PATH.exists() or LINKED_UNIT_PATH.is_symlink():
            LINKED_UNIT_PATH.unlink()
    except OSError as exc:
        raise click.ClickException(str(exc))

    _run_systemctl(["systemctl", "--user", "link", str(unit_path)], announce=announce)


def install_portforward_service(
    config_path: Optional[Path],
    *,
    project_dir: Optional[Path] = None,
    announce: bool = True,
) -> None:
    resolved_project_dir = (project_dir or Path.cwd()).resolve()
    write_systemd_env(config_path, project_dir=resolved_project_dir, announce=announce)

    unit_path = resolved_project_dir / UNIT_RELATIVE_PATH
    if not unit_path.exists():
        raise click.ClickException(tr("systemd.unit_missing", path=unit_path))

    _ensure_current_unit_link(unit_path, announce=announce)
    _run_systemctl(["systemctl", "--user", "daemon-reload"], announce=announce)
    _run_systemctl(["systemctl", "--user", "restart", SERVICE_NAME], announce=announce)
    _run_systemctl(["systemctl", "--user", "enable", SERVICE_NAME], announce=announce)


def stop_portforward_service(*, announce: bool = True) -> bool:
    if not LINKED_UNIT_PATH.exists():
        return False

    _run_systemctl(["systemctl", "--user", "stop", SERVICE_NAME], announce=announce)
    return True


def uninstall_portforward_service(*, project_dir: Optional[Path] = None, announce: bool = True) -> None:
    resolved_project_dir = (project_dir or Path.cwd()).resolve()
    unit_path = resolved_project_dir / UNIT_RELATIVE_PATH
    if not unit_path.exists():
        raise click.ClickException(tr("systemd.unit_missing", path=unit_path))

    stop_portforward_service(announce=announce)
    _run_systemctl(["systemctl", "--user", "disable", SERVICE_NAME], announce=announce)
    try:
        if LINKED_UNIT_PATH.exists():
            LINKED_UNIT_PATH.unlink()
    except OSError as exc:
        raise click.ClickException(str(exc))
    _run_systemctl(["systemctl", "--user", "daemon-reload"], announce=announce)


@click.group(name="systemd", help=tr("systemd.group_help"))
def systemd_group() -> None:
    """Команды для управления systemd-юнитами."""


@systemd_group.command(name="install", help=tr("systemd.install_help"))
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def systemd_install_command(config_path: Optional[str], non_interactive: bool) -> None:
    """Генерирует systemd.env и регистрирует unit для portforward."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    install_portforward_service(
        Path(config_path) if config_path else None,
        project_dir=Path.cwd(),
        announce=True,
    )


@systemd_group.command(name="uninstall", help=tr("systemd.uninstall_help"))
@non_interactive_option
def systemd_uninstall_command(non_interactive: bool) -> None:
    """Останавливает и удаляет systemd-юнит для portforward."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    uninstall_portforward_service(project_dir=Path.cwd(), announce=True)
