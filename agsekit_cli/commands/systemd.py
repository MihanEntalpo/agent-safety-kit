from __future__ import annotations

from dataclasses import dataclass
import platform
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import click

from ..config import DEFAULT_SYSTEMD_ENV_DIR, load_global_config_from_path, resolve_config_path
from ..i18n import tr
from . import debug_option, non_interactive_option

ENV_FILENAME = "systemd.env"
SERVICE_NAME = "agsekit-portforward"
UNIT_FILENAME = f"{SERVICE_NAME}.service"
LINKED_UNIT_PATH = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"
PACKAGED_UNIT_PATH = Path(__file__).resolve().parents[1] / "systemd" / UNIT_FILENAME
STATUS_LOG_LINES = 10


@dataclass
class SystemdServiceStatus:
    service: str
    unit_path: str
    linked_unit: str
    installed: bool
    enabled: str
    active: str
    load: str
    substate: str
    main_pid: str
    fragment_path: str
    result: str
    active_since: str
    inactive_since: str
    logs: List[str]


def is_systemd_supported_platform() -> bool:
    return platform.system() == "Linux"


def _platform_label() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macOS"
    if system == "Windows":
        return "Windows"
    return system or "this platform"


def _warn_systemd_unsupported() -> bool:
    if is_systemd_supported_platform():
        return False
    click.echo(click.style(tr("systemd.unsupported_platform", platform=_platform_label()), fg="yellow"))
    return True


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


def _query_journalctl(command: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True)


def _resolve_unit_path() -> Path:
    if PACKAGED_UNIT_PATH.exists():
        return PACKAGED_UNIT_PATH
    raise click.ClickException(tr("systemd.unit_missing", path=PACKAGED_UNIT_PATH))


def write_systemd_env(config_path: Optional[Path], *, project_dir: Optional[Path] = None, announce: bool = True) -> Path:
    resolved_project_dir = (project_dir or Path.cwd()).resolve()
    agsekit_bin = _resolve_agsekit_bin()
    resolved_config = resolve_config_path(config_path).resolve()
    global_config = load_global_config_from_path(config_path, allow_missing=True)

    env_dir = global_config.systemd_env_folder
    env_dir.mkdir(parents=True, exist_ok=True)
    env_path = env_dir / ENV_FILENAME
    compatibility_env_path = DEFAULT_SYSTEMD_ENV_DIR / ENV_FILENAME

    if env_path == compatibility_env_path and env_path.is_symlink():
        env_path.unlink()

    env_contents = (
        f"AGSEKIT_BIN={agsekit_bin}\n"
        f"AGSEKIT_CONFIG={resolved_config}\n"
        f"AGSEKIT_PROJECT_DIR={resolved_project_dir}\n"
    )
    env_path.write_text(env_contents, encoding="utf-8")
    if env_path != compatibility_env_path:
        compatibility_env_path.parent.mkdir(parents=True, exist_ok=True)
        if compatibility_env_path.exists() or compatibility_env_path.is_symlink():
            compatibility_env_path.unlink()
        compatibility_env_path.symlink_to(env_path)
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
    if not is_systemd_supported_platform():
        return
    resolved_project_dir = (project_dir or Path.cwd()).resolve()
    write_systemd_env(config_path, project_dir=resolved_project_dir, announce=announce)

    unit_path = _resolve_unit_path()
    _ensure_current_unit_link(unit_path, announce=announce)
    _run_systemctl(["systemctl", "--user", "daemon-reload"], announce=announce)
    _run_systemctl(["systemctl", "--user", "restart", SERVICE_NAME], announce=announce)
    _run_systemctl(["systemctl", "--user", "enable", SERVICE_NAME], announce=announce)


def _ensure_linked_service() -> None:
    if LINKED_UNIT_PATH.exists() or LINKED_UNIT_PATH.is_symlink():
        return
    raise click.ClickException(tr("systemd.not_installed"))


def manage_portforward_service(action: str, *, announce: bool = True) -> None:
    if not is_systemd_supported_platform():
        return
    _ensure_linked_service()
    _run_systemctl(["systemctl", "--user", action, SERVICE_NAME], announce=announce)


def stop_portforward_service(*, announce: bool = True) -> bool:
    if not is_systemd_supported_platform():
        return False
    if not LINKED_UNIT_PATH.exists():
        return False

    _run_systemctl(["systemctl", "--user", "stop", SERVICE_NAME], announce=announce)
    return True


def uninstall_portforward_service(*, project_dir: Optional[Path] = None, announce: bool = True) -> None:
    if not is_systemd_supported_platform():
        return
    del project_dir
    _resolve_unit_path()
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


def _parse_systemctl_show_output(output: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for line in output.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            parsed[key] = value.strip()
    return parsed


def _journal_lines_for_service(service_name: str) -> List[str]:
    result = _query_journalctl(
        [
            "journalctl",
            "--user",
            "-u",
            service_name,
            "-n",
            str(STATUS_LOG_LINES),
            "--no-pager",
            "-o",
            "short-iso",
        ]
    )
    if result.returncode != 0:
        return [tr("systemd.status_logs_unavailable", error=_format_systemctl_state(result))]

    lines = [line.rstrip() for line in result.stdout.splitlines() if line.strip()]
    if lines:
        return lines
    return [tr("systemd.status_logs_empty")]


def get_portforward_service_status() -> SystemdServiceStatus:
    if not is_systemd_supported_platform():
        raise click.ClickException(tr("systemd.unsupported_platform", platform=_platform_label()))
    linked_target = tr("systemd.status_not_linked")
    installed = LINKED_UNIT_PATH.exists() or LINKED_UNIT_PATH.is_symlink()
    if installed:
        linked_target = str(LINKED_UNIT_PATH.resolve(strict=False))

    enabled_result = _query_systemctl(["systemctl", "--user", "is-enabled", SERVICE_NAME])
    active_result = _query_systemctl(["systemctl", "--user", "is-active", SERVICE_NAME])
    show_result = _query_systemctl(
        [
            "systemctl",
            "--user",
            "show",
            SERVICE_NAME,
            "--property",
            ",".join(
                [
                    "LoadState",
                    "ActiveState",
                    "SubState",
                    "MainPID",
                    "FragmentPath",
                    "Result",
                    "ActiveEnterTimestamp",
                    "InactiveEnterTimestamp",
                ]
            ),
        ]
    )
    show_data = _parse_systemctl_show_output(show_result.stdout)
    logs = _journal_lines_for_service(SERVICE_NAME) if installed else []

    return SystemdServiceStatus(
        service=f"{SERVICE_NAME}.service",
        unit_path=str(_resolve_unit_path()),
        linked_unit=linked_target,
        installed=installed,
        enabled=_format_systemctl_state(enabled_result),
        active=_format_systemctl_state(active_result),
        load=show_data.get("LoadState") or tr("systemd.status_unknown"),
        substate=show_data.get("SubState") or tr("systemd.status_unknown"),
        main_pid=show_data.get("MainPID") or tr("systemd.status_unknown"),
        fragment_path=show_data.get("FragmentPath") or tr("systemd.status_unknown"),
        result=show_data.get("Result") or tr("systemd.status_unknown"),
        active_since=show_data.get("ActiveEnterTimestamp") or tr("systemd.status_unknown"),
        inactive_since=show_data.get("InactiveEnterTimestamp") or tr("systemd.status_unknown"),
        logs=logs,
    )


@click.group(name="systemd", help=tr("systemd.group_help"))
def systemd_group() -> None:
    """Команды для управления systemd-юнитами."""


@systemd_group.command(name="install", help=tr("systemd.install_help"))
@non_interactive_option
@debug_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def systemd_install_command(config_path: Optional[str], non_interactive: bool, debug: bool) -> None:
    """Генерирует systemd.env и регистрирует unit для portforward."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive
    if _warn_systemd_unsupported():
        return

    if not debug:
        click.echo(tr("systemd.installing"))
    install_portforward_service(
        Path(config_path) if config_path else None,
        project_dir=Path.cwd(),
        announce=debug,
    )
    if not debug:
        click.echo(tr("systemd.installed"))


@systemd_group.command(name="uninstall", help=tr("systemd.uninstall_help"))
@non_interactive_option
@debug_option
def systemd_uninstall_command(non_interactive: bool, debug: bool) -> None:
    """Останавливает и удаляет systemd-юнит для portforward."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive
    if _warn_systemd_unsupported():
        return

    if not debug:
        click.echo(tr("systemd.uninstalling"))
    uninstall_portforward_service(project_dir=Path.cwd(), announce=debug)
    if not debug:
        click.echo(tr("systemd.uninstalled"))


@systemd_group.command(name="start", help=tr("systemd.start_help"))
@non_interactive_option
@debug_option
def systemd_start_command(non_interactive: bool, debug: bool) -> None:
    """Запускает user-юнит для portforward."""
    del non_interactive
    if _warn_systemd_unsupported():
        return

    if not debug:
        click.echo(tr("systemd.starting"))
    manage_portforward_service("start", announce=debug)
    if not debug:
        click.echo(tr("systemd.started"))


@systemd_group.command(name="stop", help=tr("systemd.stop_help"))
@non_interactive_option
@debug_option
def systemd_stop_command(non_interactive: bool, debug: bool) -> None:
    """Останавливает user-юнит для portforward."""
    del non_interactive
    if _warn_systemd_unsupported():
        return

    if not debug:
        click.echo(tr("systemd.stopping"))
    manage_portforward_service("stop", announce=debug)
    if not debug:
        click.echo(tr("systemd.stopped"))


@systemd_group.command(name="restart", help=tr("systemd.restart_help"))
@non_interactive_option
@debug_option
def systemd_restart_command(non_interactive: bool, debug: bool) -> None:
    """Перезапускает user-юнит для portforward."""
    del non_interactive
    if _warn_systemd_unsupported():
        return

    if not debug:
        click.echo(tr("systemd.restarting"))
    manage_portforward_service("restart", announce=debug)
    if not debug:
        click.echo(tr("systemd.restarted"))


@systemd_group.command(name="status", help=tr("systemd.status_help"))
@non_interactive_option
@debug_option
def systemd_status_command(non_interactive: bool, debug: bool) -> None:
    """Показывает состояние user-юнита для portforward."""
    del non_interactive
    del debug
    if _warn_systemd_unsupported():
        return

    status = get_portforward_service_status()
    click.echo(tr("systemd.status_service", service=status.service))
    click.echo(tr("systemd.status_unit_path", path=status.unit_path))
    click.echo(tr("systemd.status_linked_unit", path=status.linked_unit))
    click.echo(tr("systemd.status_installed", state=tr("status.yes") if status.installed else tr("status.no")))
    click.echo(tr("systemd.status_enabled", state=status.enabled))
    click.echo(tr("systemd.status_active", state=status.active))
    click.echo(tr("systemd.status_load", state=status.load))
    click.echo(tr("systemd.status_substate", state=status.substate))
    click.echo(tr("systemd.status_main_pid", pid=status.main_pid))
    click.echo(tr("systemd.status_fragment_path", path=status.fragment_path))
    click.echo(tr("systemd.status_result", result=status.result))
    click.echo(tr("systemd.status_active_since", value=status.active_since))
    click.echo(tr("systemd.status_inactive_since", value=status.inactive_since))
    if status.installed:
        click.echo(tr("systemd.status_logs_header"))
        for line in status.logs:
            click.echo(tr("systemd.status_log_line", line=line))
    else:
        click.echo(tr("systemd.status_logs_skipped"))
