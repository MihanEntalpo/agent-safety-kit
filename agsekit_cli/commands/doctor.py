from __future__ import annotations

from dataclasses import dataclass
import json
import shlex
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

import click

from . import debug_option, non_interactive_option
from ..agents import configured_agent_vms
from ..agents_modules import AGENT_RUNTIME_BINARIES, get_agent_class
from ..config import AgentConfig, ConfigError, MountConfig, VmConfig, load_agents_config, load_config, load_mounts_config, load_vms_config, resolve_config_path
from ..debug import debug_log_command, debug_log_result, debug_scope
from ..host_tools import multipass_command
from ..i18n import tr
from ..mounts import RegisteredMount, host_path_has_entries, is_mount_registered, load_multipass_mounts, vm_path_has_entries
from ..vm import MultipassError, ensure_multipass_available, fetch_existing_info

DOCTOR_RESTART_RECOVERY_TIMEOUT_SECONDS = 30.0
DOCTOR_RESTART_RECOVERY_POLL_SECONDS = 1.0
DOCTOR_NODE_AGENT_BINARIES = tuple(
    sorted(
        runtime_binary
        for agent_type, runtime_binary in AGENT_RUNTIME_BINARIES.items()
        if get_agent_class(agent_type).needs_nvm()
    )
)


@dataclass
class NodeVersionIssue:
    vm_name: str
    versions_with_agents: Dict[str, List[str]]
    selected_version: str
    reinstall_agent_names: List[str]


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


def _run_vm_script(vm_name: str, script: str, *, debug: bool = False) -> subprocess.CompletedProcess[str]:
    command = [multipass_command(), "exec", vm_name, "--", "bash", "-lc", script]
    debug_log_command(command, enabled=debug)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    debug_log_result(result, enabled=debug)
    return result


def _node_version_sort_key(version: str) -> tuple[int, ...]:
    normalized = version.strip()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    parts: List[int] = []
    for part in normalized.split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            digits = "".join(ch for ch in part if ch.isdigit())
            parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _inspect_nvm_node_agents(vm_name: str, *, debug: bool = False) -> Dict[str, List[str]]:
    binaries = " ".join(shlex.quote(binary) for binary in DOCTOR_NODE_AGENT_BINARIES)
    script = "\n".join(
        [
            "set -eu",
            'export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"',
            'if [ ! -d "$NVM_DIR/versions/node" ]; then',
            "  exit 0",
            "fi",
            f"for binary in {binaries}; do",
            '  printf "BINARY\\t%s\\n" "$binary"',
            "done",
            'for version_dir in "$NVM_DIR"/versions/node/v*; do',
            '  [ -d "$version_dir" ] || continue',
            '  version="$(basename "$version_dir")"',
            '  printf "VERSION\\t%s\\n" "$version"',
            f"  for binary in {binaries}; do",
            '    if [ -x "$version_dir/bin/$binary" ]; then',
            '      printf "AGENT\\t%s\\t%s\\n" "$version" "$binary"',
            "    fi",
            "  done",
            "done",
        ]
    )
    result = _run_vm_script(vm_name, script, debug=debug)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise MultipassError(
            tr(
                "doctor.node_check_failed",
                vm_name=vm_name,
                details=f": {details}" if details else "",
            )
        )

    versions: Dict[str, List[str]] = {}
    known_binaries = set(DOCTOR_NODE_AGENT_BINARIES)
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if parts[0] == "VERSION" and len(parts) == 2:
            versions.setdefault(parts[1], [])
            continue
        if parts[0] == "AGENT" and len(parts) == 3 and parts[2] in known_binaries:
            versions.setdefault(parts[1], [])
            versions[parts[1]].append(parts[2])
            continue
        if parts[0] == "BINARY":
            continue
        raise MultipassError(tr("doctor.node_check_unexpected_output", vm_name=vm_name, output=line))

    return {
        version: sorted(set(binaries_found))
        for version, binaries_found in versions.items()
        if binaries_found
    }


def _configured_node_agents_for_vm(
    vm_name: str,
    *,
    agents_config: Dict[str, AgentConfig],
    vms_config: Dict[str, VmConfig],
) -> List[AgentConfig]:
    available_vms = vms_config.keys()
    selected: List[AgentConfig] = []
    for agent in agents_config.values():
        if not get_agent_class(agent.type).needs_nvm():
            continue
        if vm_name not in configured_agent_vms(agent, available_vms):
            continue
        selected.append(agent)
    return selected


def _find_node_version_issue_for_vm(
    vm_name: str,
    *,
    vm_states: Dict[str, str],
    agents_config: Dict[str, AgentConfig],
    vms_config: Dict[str, VmConfig],
    debug: bool = False,
) -> Optional[NodeVersionIssue]:
    if vm_states.get(vm_name) != "running":
        return None

    configured_agents = _configured_node_agents_for_vm(
        vm_name,
        agents_config=agents_config,
        vms_config=vms_config,
    )
    if not configured_agents:
        return None

    versions_with_agents = _inspect_nvm_node_agents(vm_name, debug=debug)
    if len(versions_with_agents) <= 1:
        return None

    detected_binaries = {
        binary
        for binaries_found in versions_with_agents.values()
        for binary in binaries_found
    }
    reinstall_agent_names = sorted(
        agent.name
        for agent in configured_agents
        if AGENT_RUNTIME_BINARIES[agent.type] in detected_binaries
    )
    if not reinstall_agent_names:
        return None

    selected_version = max(versions_with_agents.keys(), key=_node_version_sort_key)
    return NodeVersionIssue(
        vm_name=vm_name,
        versions_with_agents=versions_with_agents,
        selected_version=selected_version,
        reinstall_agent_names=reinstall_agent_names,
    )


def _collect_node_version_issues(
    *,
    vm_states: Dict[str, str],
    agents_config: Dict[str, AgentConfig],
    vms_config: Dict[str, VmConfig],
    debug: bool = False,
) -> List[NodeVersionIssue]:
    issues: List[NodeVersionIssue] = []
    for vm_name in vms_config.keys():
        issue = _find_node_version_issue_for_vm(
            vm_name,
            vm_states=vm_states,
            agents_config=agents_config,
            vms_config=vms_config,
            debug=debug,
        )
        if issue is not None:
            issues.append(issue)
    return issues


def _repair_node_version_issue(
    issue: NodeVersionIssue,
    *,
    config_path: Optional[str],
    debug: bool = False,
) -> None:
    from .install_agents import run_install_agents

    versions_to_remove = sorted(
        (version for version in issue.versions_with_agents if version != issue.selected_version),
        key=_node_version_sort_key,
    )
    quoted_keep = shlex.quote(issue.selected_version)
    cleanup_lines = [
        "set -eu",
        'export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"',
        '. "$NVM_DIR/nvm.sh"',
        f"nvm alias default {quoted_keep} >/dev/null",
        "nvm use --silent default >/dev/null",
    ]
    for version in versions_to_remove:
        cleanup_lines.append(f"nvm uninstall {shlex.quote(version)} >/dev/null")
    cleanup_lines.extend(
        [
            f"nvm alias default {quoted_keep} >/dev/null",
            "nvm use --silent default >/dev/null",
            "node -v",
        ]
    )
    result = _run_vm_script(issue.vm_name, "\n".join(cleanup_lines), debug=debug)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise MultipassError(
            tr(
                "doctor.node_repair_failed",
                vm_name=issue.vm_name,
                details=f": {details}" if details else "",
            )
        )

    for agent_name in issue.reinstall_agent_names:
        run_install_agents(
            agent_name=agent_name,
            vm=issue.vm_name,
            all_vms=False,
            all_agents=False,
            config_path=config_path,
            proxychains=None,
            debug=debug,
            interactive=False,
            progress=None,
        )


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
            agents_config = load_agents_config(config)
            vms_config = load_vms_config(config)
        except ConfigError as exc:
            raise click.ClickException(str(exc))

        click.echo(tr("doctor.config_path", path=resolved_path))

        if not mounts:
            click.echo(tr("doctor.no_mounts"))

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

        try:
            node_version_issues = _collect_node_version_issues(
                vm_states=vm_states,
                agents_config=agents_config,
                vms_config=vms_config,
                debug=debug,
            )
        except MultipassError as exc:
            raise click.ClickException(str(exc))

        for issue in node_version_issues:
            versions_summary = ", ".join(
                f"{version} ({', '.join(issue.versions_with_agents[version])})"
                for version in sorted(issue.versions_with_agents.keys(), key=_node_version_sort_key)
            )
            click.echo(
                tr(
                    "doctor.node_multi_version_problem",
                    vm_name=issue.vm_name,
                    versions=versions_summary,
                    selected=issue.selected_version,
                )
            )

        repairable_issue_count = len(problematic_mounts) + len(node_version_issues)
        if repairable_issue_count == 0:
            click.echo(tr("doctor.no_issues_found"))
            return

        if not assume_yes:
            if non_interactive:
                raise click.ClickException(tr("doctor.confirm_required"))
            if not click.confirm(tr("doctor.confirm_restart", count=repairable_issue_count), default=True):
                click.echo(tr("doctor.cancelled"))
                return

        click.echo(tr("doctor.repair_start", count=repairable_issue_count))

        unresolved_count = 0
        if problematic_mounts:
            click.echo(tr("doctor.rechecking"))
            try:
                _restart_multipass(debug=debug)
                _load_runtime_state_after_restart(debug=debug)
                rechecked_mounts = _recheck_problematic_mounts_after_restart(problematic_mounts, debug=debug)
            except MultipassError as exc:
                raise click.ClickException(str(exc))

            for mount, status in rechecked_mounts:
                if status == "healthy":
                    click.echo(tr("doctor.mount_repaired", source=mount.source, vm_name=mount.vm_name, target=mount.target))
                    continue

                click.echo(tr("doctor.mount_unresolved", source=mount.source, vm_name=mount.vm_name, target=mount.target))
                unresolved_count += 1

        for issue in node_version_issues:
            click.echo(
                tr(
                    "doctor.node_repair_start",
                    vm_name=issue.vm_name,
                    selected=issue.selected_version,
                    agents=", ".join(issue.reinstall_agent_names),
                )
            )
            try:
                _repair_node_version_issue(
                    issue,
                    config_path=str(resolved_path),
                    debug=debug,
                )
            except (MultipassError, ConfigError, click.ClickException) as exc:
                click.echo(
                    tr(
                        "doctor.node_multi_version_unresolved",
                        vm_name=issue.vm_name,
                        details=f": {exc}" if str(exc) else "",
                    )
                )
                unresolved_count += 1
                continue

            click.echo(
                tr(
                    "doctor.node_multi_version_repaired",
                    vm_name=issue.vm_name,
                    selected=issue.selected_version,
                    agents=", ".join(issue.reinstall_agent_names),
                )
            )

        if unresolved_count:
            raise click.ClickException(tr("doctor.repair_incomplete", count=unresolved_count))

        click.echo(tr("doctor.repair_complete"))
