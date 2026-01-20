from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

import click

from ..backup import backup_once, clean_backups, find_previous_backup
from ..agents import (
    agent_command_sequence,
    build_agent_env,
    ensure_agent_binary_available,
    ensure_vm_exists,
    find_agent,
    resolve_vm,
    run_in_vm,
    select_mount_for_source,
    start_backup_process,
)
from ..config import ConfigError, load_agents_config, load_config, load_mounts_config, load_vms_config, resolve_config_path
from ..i18n import tr
from ..vm import MultipassError
from ..mounts import MountConfig
from . import non_interactive_option

DEFAULT_WORKDIR = Path("/home/ubuntu")


def _has_existing_backup(dest_dir: Path) -> bool:
    if not dest_dir.exists() or not dest_dir.is_dir():
        return False
    try:
        return find_previous_backup(dest_dir) is not None
    except FileNotFoundError:
        return False


def _cli_entry_path() -> Path:
    argv_path = Path(sys.argv[0])
    if argv_path.name == "agsekit" and argv_path.exists():
        return argv_path.resolve()

    discovered = shutil.which("agsekit")
    if discovered:
        return Path(discovered).resolve()

    repo_entry = Path(__file__).resolve().parents[2] / "agsekit"
    if repo_entry.exists():
        return repo_entry

    raise click.ClickException(tr("run.cli_not_found"))


@click.command(name="run", context_settings={"ignore_unknown_options": True}, help=tr("run.command_help"))
@non_interactive_option
@click.argument("agent_name")
@click.argument("source_dir", required=False, type=click.Path(file_okay=False, path_type=Path))
@click.option("--vm", "vm_name", help=tr("run.option_vm"))
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
@click.option("--disable-backups", is_flag=True, help=tr("run.option_disable_backups"))
@click.option("--debug", is_flag=True, help=tr("run.option_debug"))
@click.option("--skip-default-args", is_flag=True, help=tr("run.option_skip_default_args"))
@click.option(
    "--proxychains",
    default=None,
    show_default=False,
    help=tr("run.option_proxychains"),
)
@click.argument("agent_args", nargs=-1, type=click.UNPROCESSED)
def run_command(
    agent_name: str,
    source_dir: Optional[Path],
    vm_name: Optional[str],
    config_path: Optional[str],
    disable_backups: bool,
    debug: bool,
    skip_default_args: bool,
    proxychains: Optional[str],
    agent_args: Sequence[str],
    non_interactive: bool,
) -> None:
    """Запускает интерактивную сессию агента в Multipass ВМ."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        agents_config = load_agents_config(config)
        mounts = load_mounts_config(config)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    if agent_name not in agents_config:
        available = ", ".join(sorted(agents_config.keys()))
        if available:
            raise click.ClickException(
                tr("agents.agent_not_found_with_list", name=agent_name, available=available)
            )
        raise click.ClickException(tr("agents.agent_not_found_empty", name=agent_name))

    agent = find_agent(agents_config, agent_name)

    mount_entry: Optional[MountConfig] = None
    mount_relative_path: Optional[Path] = None
    if source_dir is not None:
        try:
            mount_entry, mount_relative_path = select_mount_for_source(mounts, source_dir, vm_name)
        except ConfigError as exc:
            raise click.ClickException(str(exc))

    vm_to_use = resolve_vm(agent, mount_entry, vm_name, config)
    ensure_vm_exists(vm_to_use, vms)
    vm_config = vms[vm_to_use]

    env_vars = build_agent_env(agent)
    if mount_entry:
        relative = mount_relative_path or Path(".")
        workdir = mount_entry.target if relative == Path(".") else mount_entry.target / relative
    else:
        workdir = DEFAULT_WORKDIR

    agent_command = agent_command_sequence(agent, agent_args, skip_default_args=skip_default_args)

    click.echo(
        tr("run.starting_agent", agent=agent.name, vm_name=vm_to_use, workdir=workdir)
    )

    try:
        ensure_agent_binary_available(agent_command, vm_config, proxychains=proxychains, debug=debug)
    except MultipassError as exc:
        raise click.ClickException(str(exc))

    backup_process = None
    if not disable_backups and mount_entry is not None:
        skip_first_repeated_backup = False
        if not _has_existing_backup(mount_entry.backup):
            click.echo(tr("run.first_backup", mount_name=mount_entry.source.name))
            backup_once(mount_entry.source, mount_entry.backup, show_progress=True)
            removed = clean_backups(
                mount_entry.backup,
                mount_entry.max_backups,
                mount_entry.backup_clean_method,
                interval_minutes=mount_entry.interval_minutes,
            )
            for path in removed:
                click.echo(tr("backup_clean.removed_snapshot", path=path))
            skip_first_repeated_backup = True

        click.echo(
            tr(
                "run.starting_background_backups",
                source=mount_entry.source,
                destination=mount_entry.backup,
            )
        )
        backup_process = start_backup_process(
            mount_entry, _cli_entry_path(), skip_first=skip_first_repeated_backup, debug=debug
        )

    exit_code = 0

    try:
        exit_code = run_in_vm(vm_config, workdir, agent_command, env_vars, proxychains=proxychains, debug=debug)
    except (ConfigError, MultipassError) as exc:
        raise click.ClickException(str(exc))
    finally:
        if backup_process:
            backup_process.terminate()
            try:
                backup_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backup_process.kill()

            log_file = getattr(backup_process, "log_file", None)
            if log_file:
                log_file.close()

    if exit_code != 0:
        click.echo(tr("run.error", cmd=agent_command))
        raise SystemExit(exit_code)
