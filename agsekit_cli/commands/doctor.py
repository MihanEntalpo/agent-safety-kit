from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional, Set

import click

from . import debug_option, non_interactive_option
from ..config import ConfigError, MountConfig, load_config, load_mounts_config, resolve_config_path
from ..debug import debug_scope
from ..i18n import tr
from ..mounts import RegisteredMount, host_path_has_entries, is_mount_registered, load_multipass_mounts, vm_path_has_entries
from ..vm import MultipassError, ensure_multipass_available, fetch_existing_info

DOCTOR_RESTART_RECOVERY_TIMEOUT_SECONDS = 30.0
DOCTOR_RESTART_RECOVERY_POLL_SECONDS = 1.0


def _load_vm_states() -> Dict[str, str]:
    try:
        raw = fetch_existing_info()
    except MultipassError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise MultipassError(str(exc)) from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MultipassError(tr("doctor.multipass_parse_failed")) from exc

    states: Dict[str, str] = {}
    for item in payload.get("list", []):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        state = item.get("state")
        if isinstance(name, str) and isinstance(state, str):
            states[name] = state.lower()
    return states


def _restart_multipass(*, debug: bool = False) -> None:
    import subprocess

    from ..debug import debug_log_command, debug_log_result

    command = ["sudo", "snap", "restart", "multipass"]
    debug_log_command(command, enabled=debug)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    debug_log_result(result, enabled=debug)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise MultipassError(tr("doctor.restart_failed", details=f": {details}" if details else ""))


def _load_runtime_state(*, debug: bool = False) -> tuple[Dict[str, str], Dict[str, Set[RegisteredMount]]]:
    ensure_multipass_available()
    vm_states = _load_vm_states()
    mounted_by_vm = load_multipass_mounts(debug=debug)
    return vm_states, mounted_by_vm


def _load_runtime_state_after_restart(*, debug: bool = False) -> tuple[Dict[str, str], Dict[str, Set[RegisteredMount]]]:
    deadline = time.monotonic() + DOCTOR_RESTART_RECOVERY_TIMEOUT_SECONDS
    last_error: Optional[MultipassError] = None

    while True:
        try:
            return _load_runtime_state(debug=debug)
        except MultipassError as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                raise last_error
            time.sleep(DOCTOR_RESTART_RECOVERY_POLL_SECONDS)


def _recheck_problematic_mounts_after_restart(
    mounts: list[MountConfig],
    *,
    debug: bool = False,
) -> list[tuple[MountConfig, str]]:
    deadline = time.monotonic() + DOCTOR_RESTART_RECOVERY_TIMEOUT_SECONDS
    last_error: Optional[MultipassError] = None
    last_statuses: Optional[list[tuple[MountConfig, str]]] = None

    while True:
        try:
            vm_states, mounted_by_vm = _load_runtime_state(debug=debug)
            current_statuses: list[tuple[MountConfig, str]] = []
            for mount in mounts:
                status, _ = _is_mount_problem(mount, vm_states, mounted_by_vm, debug=debug)
                current_statuses.append((mount, status))
            last_statuses = current_statuses
            if all(status == "healthy" for _, status in current_statuses):
                return current_statuses
            last_error = None
        except MultipassError as exc:
            last_error = exc

        if time.monotonic() >= deadline:
            if last_statuses is not None:
                return last_statuses
            if last_error is not None:
                raise last_error
            return []

        time.sleep(DOCTOR_RESTART_RECOVERY_POLL_SECONDS)


def _is_mount_problem(
    mount: MountConfig,
    vm_states: Dict[str, str],
    mounted_by_vm: Dict[str, Set[RegisteredMount]],
    *,
    debug: bool = False,
) -> tuple[str, Optional[bool]]:
    host_has_entries = host_path_has_entries(mount.source)
    if host_has_entries is None:
        return "host-missing", None
    if not host_has_entries:
        return "host-empty", None

    vm_state = vm_states.get(mount.vm_name)
    if vm_state != "running":
        return "vm-not-running", None

    if not is_mount_registered(mount, mounted_by_vm):
        return "not-mounted", None

    target_has_entries = vm_path_has_entries(mount.vm_name, mount.target, debug=debug)
    if target_has_entries:
        return "healthy", True
    return "broken", False


@click.command(name="doctor", help=tr("doctor.command_help"))
@non_interactive_option
@click.option(
    "-y",
    "--yes",
    "assume_yes",
    is_flag=True,
    help=tr("doctor.option_yes"),
)
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
@debug_option
def doctor_command(
    assume_yes: bool,
    config_path: Optional[str],
    debug: bool,
    non_interactive: bool,
) -> None:
    """Run diagnostics and safe auto-repairs for known installation and configuration issues."""

    with debug_scope(debug):
        resolved_path = resolve_config_path(Path(config_path) if config_path else None)
        try:
            config = load_config(resolved_path)
            mounts = load_mounts_config(config)
        except ConfigError as exc:
            raise click.ClickException(str(exc))

        click.echo(tr("doctor.config_path", path=resolved_path))

        if not mounts:
            click.echo(tr("doctor.no_mounts"))
            return

        try:
            vm_states, mounted_by_vm = _load_runtime_state(debug=debug)
        except MultipassError as exc:
            raise click.ClickException(str(exc))

        click.echo(tr("doctor.checking"))

        problematic_mounts: list[MountConfig] = []
        for mount in mounts:
            try:
                status, _ = _is_mount_problem(mount, vm_states, mounted_by_vm, debug=debug)
            except MultipassError as exc:
                raise click.ClickException(str(exc))

            if status == "healthy":
                click.echo(tr("doctor.mount_ok", source=mount.source, vm_name=mount.vm_name, target=mount.target))
                continue
            if status == "broken":
                click.echo(tr("doctor.mount_broken", source=mount.source, vm_name=mount.vm_name, target=mount.target))
                problematic_mounts.append(mount)
                continue
            if status == "host-missing":
                click.echo(tr("doctor.mount_skipped_host_missing", source=mount.source))
                continue
            if status == "host-empty":
                click.echo(tr("doctor.mount_skipped_host_empty", source=mount.source))
                continue
            if status == "not-mounted":
                click.echo(tr("doctor.mount_skipped_not_mounted", source=mount.source, vm_name=mount.vm_name))
                continue
            click.echo(tr("doctor.mount_skipped_vm_not_running", source=mount.source, vm_name=mount.vm_name))

        if not problematic_mounts:
            click.echo(tr("doctor.no_issues_found"))
            return

        if not assume_yes:
            if non_interactive:
                raise click.ClickException(tr("doctor.confirm_required"))
            if not click.confirm(tr("doctor.confirm_restart", count=len(problematic_mounts)), default=True):
                click.echo(tr("doctor.cancelled"))
                return

        click.echo(tr("doctor.repair_start", count=len(problematic_mounts)))
        click.echo(tr("doctor.rechecking"))
        try:
            _restart_multipass(debug=debug)
            _load_runtime_state_after_restart(debug=debug)
            rechecked_mounts = _recheck_problematic_mounts_after_restart(problematic_mounts, debug=debug)
        except MultipassError as exc:
            raise click.ClickException(str(exc))

        unresolved: list[MountConfig] = []
        for mount, status in rechecked_mounts:
            if status == "healthy":
                click.echo(tr("doctor.mount_repaired", source=mount.source, vm_name=mount.vm_name, target=mount.target))
                continue

            click.echo(tr("doctor.mount_unresolved", source=mount.source, vm_name=mount.vm_name, target=mount.target))
            unresolved.append(mount)

        if unresolved:
            raise click.ClickException(tr("doctor.repair_incomplete", count=len(unresolved)))

        click.echo(tr("doctor.repair_complete"))
