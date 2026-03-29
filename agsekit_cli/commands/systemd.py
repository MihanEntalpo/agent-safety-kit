from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import click

from ..config import DEFAULT_CONFIG_PATH, resolve_config_path
from ..i18n import tr
from . import non_interactive_option

ENV_FILENAME = "systemd.env"
SERVICE_NAME = "agsekit-portforward"
UNIT_FILENAME = f"{SERVICE_NAME}.service"
UNIT_RELATIVE_PATH = Path("systemd") / UNIT_FILENAME
LINKED_UNIT_PATH = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"
PACKAGED_UNIT_PATH = Path(__file__).resolve().parents[1] / "systemd" / UNIT_FILENAME
REPO_UNIT_PATH = Path(__file__).resolve().parents[2] / UNIT_RELATIVE_PATH


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


def _query_systemctl(command: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True)


def _resolve_unit_path(*, project_dir: Optional[Path] = None) -> Path:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in (
        PACKAGED_UNIT_PATH,
        REPO_UNIT_PATH,
        ((project_dir.resolve() if project_dir else None) / UNIT_RELATIVE_PATH) if project_dir else None,
    ):
        if candidate is None:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise click.ClickException(tr("systemd.unit_missing", path=candidates[0]))


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

    unit_path = _resolve_unit_path(project_dir=resolved_project_dir)
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
    _resolve_unit_path(project_dir=(project_dir or Path.cwd()).resolve())
    stop_portforward_service(announce=announce)
    _run_systemctl(["systemctl", "--user", "disable", SERVICE_NAME], announce=announce)
    try:
        if LINKED_UNIT_PATH.exists():
            LINKED_UNIT_PATH.unlink()
    except OSError as exc:
        raise click.ClickException(str(exc))
    _run_systemctl(["systemctl", "--user", "daemon-reload"], announce=announce)


def _format_systemctl_state(result: subprocess.CompletedProcess[str]) -> str:
    for value in (result.stdout.strip(), result.stderr.strip()):
        if value:
            return value
    return tr("systemd.status_unknown")


def get_portforward_service_status() -> Dict[str, str]:
    linked_target = tr("systemd.status_not_linked")
    if LINKED_UNIT_PATH.exists() or LINKED_UNIT_PATH.is_symlink():
        linked_target = str(LINKED_UNIT_PATH.resolve(strict=False))

    enabled_result = _query_systemctl(["systemctl", "--user", "is-enabled", SERVICE_NAME])
    active_result = _query_systemctl(["systemctl", "--user", "is-active", SERVICE_NAME])

    return {
        "service": f"{SERVICE_NAME}.service",
        "unit_path": str(_resolve_unit_path()),
        "linked_unit": linked_target,
        "enabled": _format_systemctl_state(enabled_result),
        "active": _format_systemctl_state(active_result),
    }


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


@systemd_group.command(name="status", help=tr("systemd.status_help"))
@non_interactive_option
def systemd_status_command(non_interactive: bool) -> None:
    """Показывает состояние user-юнита для portforward."""
    del non_interactive

    status = get_portforward_service_status()
    click.echo(tr("systemd.status_service", service=status["service"]))
    click.echo(tr("systemd.status_unit_path", path=status["unit_path"]))
    click.echo(tr("systemd.status_linked_unit", path=status["linked_unit"]))
    click.echo(tr("systemd.status_enabled", state=status["enabled"]))
    click.echo(tr("systemd.status_active", state=status["active"]))
