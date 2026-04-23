from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from ..daemon_backends import get_daemon_backend, platform_label
from ..i18n import tr
from . import debug_option, non_interactive_option


def _warn_daemon_unsupported() -> bool:
    backend = get_daemon_backend()
    if backend.supported:
        return False
    click.echo(click.style(tr("daemon.unsupported_platform", platform=platform_label()), fg="yellow"))
    return True


def run_daemon_install(config_path: Optional[str], *, debug: bool) -> None:
    if _warn_daemon_unsupported():
        return
    if not debug:
        click.echo(tr("daemon.installing"))
    get_daemon_backend().install(Path(config_path) if config_path else None, project_dir=Path.cwd(), announce=debug)
    if not debug:
        click.echo(tr("daemon.installed"))


def run_daemon_uninstall(*, debug: bool) -> None:
    if _warn_daemon_unsupported():
        return
    if not debug:
        click.echo(tr("daemon.uninstalling"))
    get_daemon_backend().uninstall(project_dir=Path.cwd(), announce=debug)
    if not debug:
        click.echo(tr("daemon.uninstalled"))


def run_daemon_start(*, debug: bool) -> None:
    if _warn_daemon_unsupported():
        return
    if not debug:
        click.echo(tr("daemon.starting"))
    get_daemon_backend().start(announce=debug)
    if not debug:
        click.echo(tr("daemon.started"))


def run_daemon_stop(*, debug: bool) -> None:
    if _warn_daemon_unsupported():
        return
    if not debug:
        click.echo(tr("daemon.stopping"))
    get_daemon_backend().stop(announce=debug)
    if not debug:
        click.echo(tr("daemon.stopped"))


def run_daemon_restart(*, debug: bool) -> None:
    if _warn_daemon_unsupported():
        return
    if not debug:
        click.echo(tr("daemon.restarting"))
    get_daemon_backend().restart(announce=debug)
    if not debug:
        click.echo(tr("daemon.restarted"))


def run_daemon_status() -> None:
    if _warn_daemon_unsupported():
        return
    for line in get_daemon_backend().status_lines():
        click.echo(line)


@click.group(name="daemon", help=tr("daemon.group_help"))
def daemon_group() -> None:
    """Commands for managing the portforward daemon."""


@daemon_group.command(name="install", help=tr("daemon.install_help"))
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
def daemon_install_command(config_path: Optional[str], non_interactive: bool, debug: bool) -> None:
    del non_interactive
    run_daemon_install(config_path, debug=debug)


@daemon_group.command(name="uninstall", help=tr("daemon.uninstall_help"))
@non_interactive_option
@debug_option
def daemon_uninstall_command(non_interactive: bool, debug: bool) -> None:
    del non_interactive
    run_daemon_uninstall(debug=debug)


@daemon_group.command(name="start", help=tr("daemon.start_help"))
@non_interactive_option
@debug_option
def daemon_start_command(non_interactive: bool, debug: bool) -> None:
    del non_interactive
    run_daemon_start(debug=debug)


@daemon_group.command(name="stop", help=tr("daemon.stop_help"))
@non_interactive_option
@debug_option
def daemon_stop_command(non_interactive: bool, debug: bool) -> None:
    del non_interactive
    run_daemon_stop(debug=debug)


@daemon_group.command(name="restart", help=tr("daemon.restart_help"))
@non_interactive_option
@debug_option
def daemon_restart_command(non_interactive: bool, debug: bool) -> None:
    del non_interactive
    run_daemon_restart(debug=debug)


@daemon_group.command(name="status", help=tr("daemon.status_help"))
@non_interactive_option
@debug_option
def daemon_status_command(non_interactive: bool, debug: bool) -> None:
    del non_interactive
    del debug
    run_daemon_status()
