from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional, Union

import click

from ..config import CONFIG_ENV_VAR, DEFAULT_CONFIG_PATH, resolve_config_path
from ..i18n import tr
from ..progress import ProgressManager, SingleTaskProgressProxy
from . import debug_option, non_interactive_option
from .create_vm import run_create_vms
from .install_agents import run_install_agents
from .prepare import run_prepare


@click.command(name="up", help=tr("up.command_help"))
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
@click.option("--prepare/--no-prepare", "do_prepare", default=True, help=tr("up.option_prepare"))
@click.option("--create-vms/--no-create-vms", "do_create_vms", default=True, help=tr("up.option_create_vms"))
@click.option(
    "--install-agents/--no-install-agents",
    "do_install_agents",
    default=True,
    help=tr("up.option_install_agents"),
)
def up_command(
    non_interactive: bool,
    config_path: Optional[str],
    debug: bool,
    do_prepare: bool,
    do_create_vms: bool,
    do_install_agents: bool,
) -> None:
    """Prepare host, create VMs, and install agents without prompts."""
    del non_interactive

    if not any((do_prepare, do_create_vms, do_install_agents)):
        raise click.ClickException(tr("up.no_stages_selected"))

    config_required = do_create_vms or do_install_agents
    explicit_or_env_config = config_path is not None or os.environ.get(CONFIG_ENV_VAR)
    resolved_config_path = resolve_config_path(Path(config_path) if config_path else None)
    if config_required and not resolved_config_path.exists():
        if explicit_or_env_config:
            raise click.ClickException(tr("config.file_not_found", path=resolved_config_path))
        raise click.ClickException(tr("up.default_config_missing", path=DEFAULT_CONFIG_PATH))

    stages: list[tuple[str, Callable[[Union[ProgressManager, SingleTaskProgressProxy]], None], bool]] = []
    if do_prepare:
        stages.append((tr("progress.up_stage_prepare"), lambda progress: run_prepare(debug=debug, progress=progress), False))
    if do_create_vms:
        stages.append(
            (
                tr("progress.up_stage_create_vms"),
                lambda progress: run_create_vms(config_path, debug=debug, progress=progress),
                True,
            )
        )
    if do_install_agents:
        stages.append(
            (
                tr("progress.up_stage_install_agents"),
                lambda progress: run_install_agents(
                    agent_name=None,
                    vm=None,
                    all_vms=False,
                    all_agents=True,
                    config_path=config_path,
                    proxychains=None,
                    debug=debug,
                    interactive=False,
                    progress=progress,
                ),
                True,
            )
        )

    with ProgressManager(debug=debug) as progress:
        overall_task = progress.add_task(tr("progress.up_title"), total=len(stages))
        for stage_name, stage_runner, use_detail_proxy in stages:
            progress.update(overall_task, description=stage_name)
            if use_detail_proxy:
                with SingleTaskProgressProxy(progress) as detail_progress:
                    stage_runner(detail_progress)
            else:
                stage_runner(progress)
            progress.advance(overall_task)
