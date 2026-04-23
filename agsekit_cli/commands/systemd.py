from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from .. import systemd_backend
from ..config import DEFAULT_SYSTEMD_ENV_DIR
from ..i18n import tr
from . import debug_option, non_interactive_option
from . import daemon as daemon_command

ENV_FILENAME = systemd_backend.ENV_FILENAME
SERVICE_NAME = systemd_backend.SERVICE_NAME
UNIT_FILENAME = systemd_backend.UNIT_FILENAME
LINKED_UNIT_PATH = systemd_backend.LINKED_UNIT_PATH
PACKAGED_UNIT_PATH = systemd_backend.PACKAGED_UNIT_PATH
SystemdServiceStatus = systemd_backend.SystemdServiceStatus


def is_systemd_supported_platform() -> bool:
    return systemd_backend.is_systemd_supported_platform()


def _platform_label() -> str:
    return systemd_backend.platform_label()


def _resolve_agsekit_bin() -> Path:
    return systemd_backend.resolve_agsekit_bin()


def _run_systemctl(command, *, announce=True):
    return systemd_backend.run_systemctl(command, announce=announce)


def _query_systemctl(command):
    return systemd_backend.query_systemctl(command)


def _query_journalctl(command):
    return systemd_backend.query_journalctl(command)


def write_systemd_env(config_path: Optional[Path], *, project_dir: Optional[Path] = None, announce: bool = True) -> Path:
    return systemd_backend.write_systemd_env(config_path, project_dir=project_dir, announce=announce)


def install_portforward_service(config_path: Optional[Path], *, project_dir: Optional[Path] = None, announce: bool = True) -> None:
    return systemd_backend.install_portforward_service(config_path, project_dir=project_dir, announce=announce)


def manage_portforward_service(action: str, *, announce: bool = True) -> None:
    return systemd_backend.manage_portforward_service(action, announce=announce)


def stop_portforward_service(*, announce: bool = True) -> bool:
    return systemd_backend.stop_portforward_service(announce=announce)


def uninstall_portforward_service(*, project_dir: Optional[Path] = None, announce: bool = True) -> None:
    return systemd_backend.uninstall_portforward_service(project_dir=project_dir, announce=announce)


def get_portforward_service_status() -> SystemdServiceStatus:
    return systemd_backend.get_portforward_service_status()


def _warn_systemd_alias(action: str) -> None:
    click.echo(click.style(tr("systemd.deprecated_alias", action=action), fg="yellow"))


@click.group(name="systemd", help=tr("systemd.group_help"))
def systemd_group() -> None:
    """Deprecated alias for daemon commands."""


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
    del non_interactive
    _warn_systemd_alias("install")
    daemon_command.run_daemon_install(config_path, debug=debug)


@systemd_group.command(name="uninstall", help=tr("systemd.uninstall_help"))
@non_interactive_option
@debug_option
def systemd_uninstall_command(non_interactive: bool, debug: bool) -> None:
    del non_interactive
    _warn_systemd_alias("uninstall")
    daemon_command.run_daemon_uninstall(debug=debug)


@systemd_group.command(name="start", help=tr("systemd.start_help"))
@non_interactive_option
@debug_option
def systemd_start_command(non_interactive: bool, debug: bool) -> None:
    del non_interactive
    _warn_systemd_alias("start")
    daemon_command.run_daemon_start(debug=debug)


@systemd_group.command(name="stop", help=tr("systemd.stop_help"))
@non_interactive_option
@debug_option
def systemd_stop_command(non_interactive: bool, debug: bool) -> None:
    del non_interactive
    _warn_systemd_alias("stop")
    daemon_command.run_daemon_stop(debug=debug)


@systemd_group.command(name="restart", help=tr("systemd.restart_help"))
@non_interactive_option
@debug_option
def systemd_restart_command(non_interactive: bool, debug: bool) -> None:
    del non_interactive
    _warn_systemd_alias("restart")
    daemon_command.run_daemon_restart(debug=debug)


@systemd_group.command(name="status", help=tr("systemd.status_help"))
@non_interactive_option
@debug_option
def systemd_status_command(non_interactive: bool, debug: bool) -> None:
    del non_interactive
    del debug
    _warn_systemd_alias("status")
    daemon_command.run_daemon_status()
