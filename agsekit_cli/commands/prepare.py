from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from ..config import load_global_config_from_path
from ..debug import debug_scope
from ..i18n import tr
from ..prepare_strategies import choose_prepare
from ..progress import ProgressManager
from ..vm_prepare import ensure_host_ssh_keypair
from . import debug_option, non_interactive_option


def _prepare_host_dependencies(*, quiet: bool = False) -> None:
    choose_prepare(quiet=quiet).prepare_host()


def run_prepare(*, debug: bool, config_path: Optional[str] = None, progress: Optional[ProgressManager] = None) -> None:
    task_id = None

    def _update(description: str) -> None:
        if progress and task_id is not None:
            progress.update(task_id, description=description)

    def _advance() -> None:
        if progress and task_id is not None:
            progress.advance(task_id)

    global_config = load_global_config_from_path(
        Path(config_path) if config_path else None,
        allow_missing=True,
    )

    with debug_scope(debug):
        _update(tr("progress.up_prepare_multipass"))
        if progress and hasattr(progress, "suspend"):
            with progress.suspend():
                _prepare_host_dependencies(quiet=True)
        else:
            _prepare_host_dependencies(quiet=progress is not None)
        _advance()

        _update(tr("progress.up_prepare_ssh"))
        if not progress:
            click.echo(tr("prepare.ensure_keypair"))
        ensure_host_ssh_keypair(ssh_dir=global_config.ssh_keys_folder, verbose=debug)
        _advance()


@click.command(name="prepare", help=tr("prepare.command_help"))
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
@debug_option
def prepare_command(non_interactive: bool, config_path: Optional[str], debug: bool) -> None:
    """Install Multipass dependencies on supported hosts and prepare VMs."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive
    run_prepare(debug=debug, config_path=config_path)
