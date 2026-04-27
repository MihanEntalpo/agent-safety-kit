from __future__ import annotations

import shutil
import secrets
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
    resolve_http_proxy,
    resolve_vm,
    run_in_vm,
    start_backup_process,
)
from ..config import (
    ConfigError,
    HttpProxyConfig,
    _normalize_http_proxy,
    load_agents_config,
    load_config,
    load_global_config,
    load_mounts_config,
    load_vms_config,
    resolve_config_path,
)
from ..debug import debug_log_command, debug_log_result, debug_scope
from ..host_tools import multipass_command
from ..i18n import tr
from ..vm import MultipassError, ensure_multipass_available
from ..vm import resolve_proxychains as resolve_effective_proxychains
from ..mounts import (
    MountAlreadyMountedError,
    MountConfig,
    find_mount_by_path,
    host_path_has_entries,
    is_mount_registered,
    load_multipass_mounts,
    mount_directory,
    normalize_path,
    vm_path_has_entries,
)
from ..progress import StatusSpinner
from . import debug_option, non_interactive_option


def _create_temp_vm_workdir(vm_name: str, *, debug: bool = False) -> Path:
    ensure_multipass_available()
    workdir = Path(f"/tmp/run-{secrets.token_hex(6)}")
    command = [multipass_command(), "exec", vm_name, "--", "mkdir", "-p", str(workdir)]
    debug_log_command(command, enabled=debug)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    debug_log_result(result, enabled=debug)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise MultipassError(details or tr("run.temp_workdir_create_failed", vm_name=vm_name, path=workdir))
    return workdir


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


def _vm_directory_is_empty_while_host_has_files(
    mount_entry: Optional[MountConfig],
    local_path: Optional[Path],
    vm_path: Path,
    *,
    debug: bool = False,
) -> bool:
    if mount_entry is None or local_path is None:
        return False

    host_has_entries = host_path_has_entries(local_path)
    if not host_has_entries:
        return False

    mounted_by_vm = load_multipass_mounts(debug=debug)
    if not is_mount_registered(mount_entry, mounted_by_vm):
        return False

    if vm_path_has_entries(mount_entry.vm_name, vm_path, debug=debug):
        return False

    return True


def _ensure_mount_registered_for_run(
    mount_entry: Optional[MountConfig],
    *,
    debug: bool = False,
    non_interactive: bool = False,
    auto_mount: bool = False,
) -> bool:
    if mount_entry is None:
        return True

    mounted_by_vm = load_multipass_mounts(debug=debug)
    if is_mount_registered(mount_entry, mounted_by_vm):
        return True

    if auto_mount:
        should_mount = True
    else:
        should_mount = False

    if non_interactive:
        if not auto_mount:
            raise click.ClickException(
                tr("run.mount_confirm_required", source=mount_entry.source, vm_name=mount_entry.vm_name, target=mount_entry.target)
            )
    elif not auto_mount:
        should_mount = click.confirm(tr("run.mount_confirm", source=normalize_path(mount_entry.source)), default=True)

    if not should_mount:
        return False

    try:
        mount_directory(mount_entry)
    except MountAlreadyMountedError:
        return True

    click.echo(
        tr(
            "mounts.mounted",
            source=normalize_path(mount_entry.source),
            vm_name=mount_entry.vm_name,
            target=mount_entry.target,
        )
    )
    return True


def _apply_direct_http_proxy_env(env_vars: dict, http_proxy: HttpProxyConfig) -> None:
    if http_proxy.url is None:
        raise ConfigError(tr("run.http_proxy_invalid_runtime"))
    env_vars["HTTP_PROXY"] = http_proxy.url
    env_vars["http_proxy"] = http_proxy.url


@click.command(
    name="run",
    context_settings={"allow_interspersed_args": False},
    help=tr("run.command_help"),
)
@non_interactive_option
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
@click.option("--first-backup", "first_backup_override", flag_value=True, default=None, help=tr("run.option_first_backup"))
@click.option("--no-first-backup", "first_backup_override", flag_value=False, help=tr("run.option_no_first_backup"))
@click.option("--auto-mount", is_flag=True, help=tr("run.option_auto_mount"))
@click.option(
    "--workdir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=tr("run.option_workdir"),
)
@debug_option
@click.option("--skip-default-args", is_flag=True, help=tr("run.option_skip_default_args"))
@click.option(
    "--proxychains",
    default=None,
    show_default=False,
    help=tr("run.option_proxychains"),
)
@click.option(
    "--http-proxy",
    default=None,
    show_default=False,
    help=tr("run.option_http_proxy"),
)
@click.argument("agent_name")
@click.argument("agent_args", nargs=-1, type=click.UNPROCESSED)
def run_command(
    vm_name: Optional[str],
    config_path: Optional[str],
    disable_backups: bool,
    first_backup_override: Optional[bool],
    auto_mount: bool,
    workdir: Optional[Path],
    debug: bool,
    skip_default_args: bool,
    proxychains: Optional[str],
    http_proxy: Optional[str],
    agent_name: str,
    agent_args: Sequence[str],
    non_interactive: bool,
) -> None:
    """Запускает интерактивную сессию агента в Multipass ВМ."""
    with debug_scope(debug):
        with StatusSpinner(enabled=not debug, spinner="dots") as status:
            status.update(tr("run.progress_launch_prep"))

            resolved_path = resolve_config_path(Path(config_path) if config_path else None)
            try:
                config = load_config(resolved_path)
                global_config = load_global_config(config)
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
            proxychains_override = proxychains
            if proxychains_override is None and agent.proxychains_defined:
                proxychains_override = agent.proxychains if agent.proxychains is not None else ""

            mount_entry: Optional[MountConfig] = None
            mount_relative_path: Optional[Path] = None

            source_to_resolve = workdir or Path.cwd()
            use_temp_vm_workdir = False
            if source_to_resolve.is_dir():
                candidate_mounts = [mount for mount in mounts if vm_name is None or mount.vm_name == vm_name]
                try:
                    mount_entry = find_mount_by_path(candidate_mounts, source_to_resolve)
                except ConfigError as exc:
                    raise click.ClickException(str(exc))
                if mount_entry is None:
                    if non_interactive:
                        suffix = tr("agents.mount_not_found_vm_suffix", vm_name=vm_name) if vm_name else ""
                        raise click.ClickException(
                            tr("agents.mount_not_found", path=normalize_path(source_to_resolve), suffix=suffix)
                        )
                    with status.suspend():
                        if not click.confirm(tr("run.unconfigured_workdir_temp_confirm"), default=False):
                            return
                    use_temp_vm_workdir = True
                else:
                    mount_relative_path = normalize_path(source_to_resolve).relative_to(mount_entry.source)
            else:
                if non_interactive:
                    raise click.ClickException(tr("run.workdir_missing", path=normalize_path(source_to_resolve)))
                with status.suspend():
                    if not click.confirm(tr("run.missing_workdir_temp_confirm"), default=False):
                        return
                use_temp_vm_workdir = True

            vm_to_use = resolve_vm(agent, mount_entry, vm_name, config)
            ensure_vm_exists(vm_to_use, vms)
            vm_config = vms[vm_to_use]
            effective_http_proxy = resolve_http_proxy(agent, vm_config)
            if http_proxy is not None:
                try:
                    effective_http_proxy = _normalize_http_proxy(http_proxy, "run.--http-proxy")
                except ConfigError as exc:
                    raise click.ClickException(str(exc))
            effective_proxychains = resolve_effective_proxychains(vm_config, proxychains_override)

            effective_allowed_agents = vm_config.allowed_agents
            restricted_by_mount = False
            if mount_entry and mount_entry.allowed_agents is not None:
                effective_allowed_agents = mount_entry.allowed_agents
                restricted_by_mount = True

            if effective_allowed_agents is not None and agent.name not in effective_allowed_agents:
                allowed_agents = ", ".join(effective_allowed_agents) if effective_allowed_agents else "-"
                if restricted_by_mount and mount_entry is not None:
                    raise click.ClickException(
                        tr(
                            "run.agent_not_allowed_for_mount",
                            agent_name=agent.name,
                            source=mount_entry.source,
                            allowed_agents=allowed_agents,
                        )
                    )
                raise click.ClickException(
                    tr(
                        "run.agent_not_allowed_for_vm",
                        agent_name=agent.name,
                        vm_name=vm_to_use,
                        allowed_agents=allowed_agents,
                    )
                )

            env_vars = build_agent_env(agent)
            if effective_http_proxy is not None and effective_http_proxy.is_direct():
                _apply_direct_http_proxy_env(env_vars, effective_http_proxy)
            workdir_in_vm: Optional[Path]
            if use_temp_vm_workdir:
                workdir_in_vm = None
            else:
                if mount_entry is None:
                    raise click.ClickException(tr("run.workdir_missing", path=normalize_path(source_to_resolve)))
                relative = mount_relative_path or Path(".")
                workdir_in_vm = mount_entry.target if relative == Path(".") else mount_entry.target / relative

            agent_command = agent_command_sequence(agent, agent_args, skip_default_args=skip_default_args)

            if effective_http_proxy is not None and effective_proxychains is not None:
                raise click.ClickException(tr("run.http_proxy_proxychains_conflict"))

            status.update(tr("run.progress_mount_check"))
            try:
                should_continue = _ensure_mount_registered_for_run(
                    mount_entry,
                    debug=debug,
                    non_interactive=non_interactive,
                    auto_mount=auto_mount,
                )
            except MultipassError as exc:
                raise click.ClickException(str(exc))
            if not should_continue:
                return

            warning_source_dir = normalize_path(source_to_resolve) if mount_entry is not None and source_to_resolve is not None else None
            try:
                status.update(tr("run.progress_mount_visibility"))
                should_warn_about_empty_vm_dir = _vm_directory_is_empty_while_host_has_files(
                    mount_entry,
                    warning_source_dir,
                    workdir_in_vm,
                    debug=debug,
                )
                if should_warn_about_empty_vm_dir and warning_source_dir is not None:
                    with status.suspend():
                        click.echo(tr("run.mount_empty_warning", source_dir=warning_source_dir))
                        click.confirm(tr("run.mount_empty_confirm"), default=False, abort=True)
            except MultipassError:
                pass

            if workdir_in_vm is None:
                status.update(tr("run.progress_temp_workdir"))
                try:
                    workdir_in_vm = _create_temp_vm_workdir(vm_to_use, debug=debug)
                except MultipassError as exc:
                    raise click.ClickException(str(exc))
                with status.suspend():
                    click.echo(tr("run.temp_workdir_created", path=workdir_in_vm))

            with status.suspend():
                click.echo(
                    tr("run.starting_agent", agent=agent.name, vm_name=vm_to_use, workdir=workdir_in_vm)
                )

            backup_process = None
            if mount_entry is not None:
                skip_first_repeated_backup = False
                existing_backup_exists = _has_existing_backup(mount_entry.backup)
                effective_first_backup = (
                    mount_entry.first_backup if first_backup_override is None else first_backup_override
                )
                needs_blocking_backup = (not existing_backup_exists) or effective_first_backup
                if needs_blocking_backup:
                    status.update(tr("run.progress_blocking_backup"))
                    with status.suspend():
                        if existing_backup_exists:
                            click.echo(tr("run.backup_before_start", mount_name=mount_entry.source.name))
                        else:
                            click.echo(tr("run.first_backup", mount_name=mount_entry.source.name))
                        backup_once(
                            mount_entry.source,
                            mount_entry.backup,
                            show_progress=True,
                            announce_snapshot_created=False,
                        )
                    removed = clean_backups(
                        mount_entry.backup,
                        mount_entry.max_backups,
                        mount_entry.backup_clean_method,
                        interval_minutes=mount_entry.interval_minutes,
                    )
                    skip_first_repeated_backup = True

                if not disable_backups:
                    status.update(tr("run.progress_background_backups"))
                    with status.suspend():
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
                run_in_vm_kwargs = {
                    "proxychains": None if effective_http_proxy is not None else proxychains_override,
                    "debug": debug,
                }
                if effective_http_proxy is not None and not effective_http_proxy.is_direct():
                    run_in_vm_kwargs["http_proxy"] = effective_http_proxy
                    run_in_vm_kwargs["http_proxy_port_pool"] = global_config.http_proxy_port_pool

                with status.suspend():
                    exit_code = run_in_vm(
                        vm_config,
                        workdir_in_vm,
                        agent_command,
                        env_vars,
                        **run_in_vm_kwargs,
                    )
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
