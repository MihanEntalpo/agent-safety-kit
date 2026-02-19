from __future__ import annotations

import json
import re
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import click

from . import non_interactive_option
from ..backup import list_backup_snapshots
from ..config import (
    AgentConfig,
    ConfigError,
    MountConfig,
    VmConfig,
    load_agents_config,
    load_config,
    load_mounts_config,
    load_vms_config,
    resolve_config_path,
)
from ..i18n import tr
from ..vm import fetch_existing_info, to_bytes

NODE_AGENT_BINARIES = {"codex", "qwen", "qwen-code"}
NVM_LOAD_SNIPPET = (
    "export NVM_DIR=${NVM_DIR:-$HOME/.nvm}; "
    "if [ -s \"$NVM_DIR/nvm.sh\" ]; then . \"$NVM_DIR/nvm.sh\"; "
    "elif [ -s \"$NVM_DIR/bash_completion\" ]; then . \"$NVM_DIR/bash_completion\"; fi"
)


def _human_size(value: Optional[int]) -> str:
    if value is None:
        return tr("status.size_unknown")
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024.0 or unit == "TB":
            if unit in {"B", "KB"}:
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024.0
    return f"{int(value)} B"


def _load_multipass_entries() -> tuple[Dict[str, Dict[str, object]], Optional[str]]:
    try:
        raw = fetch_existing_info()
    except Exception as exc:  # pragma: no cover - defensive
        return {}, str(exc)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}, tr("status.multipass_parse_failed")

    entries: Dict[str, Dict[str, object]] = {}
    for item in payload.get("list", []):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str):
            entries[name] = item
    return entries, None


def _load_multipass_info_entries() -> tuple[Dict[str, Dict[str, object]], Optional[str]]:
    result = subprocess.run(
        ["multipass", "info", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}, result.stderr.strip() or tr("status.multipass_parse_failed")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}, tr("status.multipass_parse_failed")

    info = payload.get("info")
    if not isinstance(info, dict):
        return {}, tr("status.multipass_parse_failed")

    entries: Dict[str, Dict[str, object]] = {}
    for name, value in info.items():
        if isinstance(name, str) and isinstance(value, dict):
            entries[name] = value
    return entries, None


def _is_portforward_running() -> Optional[bool]:
    result = subprocess.run(["ps", "-eo", "args="], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "agsekit portforward" in stripped:
            return True
        if "agsekit_cli.cli" in stripped and "portforward" in stripped:
            return True
    return False


def _format_real_suffix(actual: str, mismatch: bool) -> str:
    if not mismatch:
        return ""
    value = click.style(actual, fg="red")
    return f" ({tr('status.real_prefix')}: {value})"


def _extract_port(value: Optional[str]) -> str:
    if not value:
        return "?"
    return value.rsplit(":", 1)[-1]


def _to_bytes_deep(value: object) -> Optional[int]:
    direct = to_bytes(value)
    if direct is not None:
        return direct

    if not isinstance(value, dict):
        return None

    for key in ("total", "size", "limit", "max"):
        if key in value:
            parsed = _to_bytes_deep(value[key])
            if parsed is not None:
                return parsed

    nested_totals: List[int] = []
    for nested in value.values():
        if isinstance(nested, dict):
            parsed = _to_bytes_deep(nested)
            if parsed is not None:
                nested_totals.append(parsed)
    if nested_totals:
        return sum(nested_totals)
    return None


def _extract_cpu_count(list_entry: Optional[Dict[str, object]], info_entry: Optional[Dict[str, object]]) -> Optional[str]:
    for source in (list_entry, info_entry):
        if not source:
            continue
        for key in ("cpus", "cpu_count", "cpu-count"):
            value = source.get(key)
            if isinstance(value, (int, float)):
                return str(int(value))
            if isinstance(value, str) and value.strip():
                return value.strip()
        cpu_payload = source.get("cpu")
        if isinstance(cpu_payload, dict):
            count = cpu_payload.get("count")
            if isinstance(count, (int, float)):
                return str(int(count))
            if isinstance(count, str) and count.strip():
                return count.strip()
    return None


def _extract_ram_bytes(list_entry: Optional[Dict[str, object]], info_entry: Optional[Dict[str, object]]) -> Optional[int]:
    candidates: List[object] = []
    if list_entry:
        candidates.extend(
            [
                list_entry.get("mem"),
                list_entry.get("memory"),
                list_entry.get("memory_total"),
                list_entry.get("ram"),
            ]
        )
    if info_entry:
        candidates.extend(
            [
                info_entry.get("memory"),
                info_entry.get("mem"),
                info_entry.get("memory_total"),
                info_entry.get("ram"),
            ]
        )

    for candidate in candidates:
        if candidate is None:
            continue
        parsed = _to_bytes_deep(candidate)
        if parsed is not None:
            return parsed
    return None


def _extract_disk_bytes(list_entry: Optional[Dict[str, object]], info_entry: Optional[Dict[str, object]]) -> Optional[int]:
    candidates: List[object] = []
    if list_entry:
        candidates.extend(
            [
                list_entry.get("disk"),
                list_entry.get("disk_total"),
                list_entry.get("disk_space"),
            ]
        )
    if info_entry:
        candidates.extend(
            [
                info_entry.get("disk"),
                info_entry.get("disks"),
                info_entry.get("disk_total"),
            ]
        )

    for candidate in candidates:
        if candidate is None:
            continue
        parsed = _to_bytes_deep(candidate)
        if parsed is not None:
            return parsed
    return None


def _format_port_forwarding(rules: Sequence[object]) -> str:
    from ..config import PortForwardingRule

    if not rules:
        return tr("status.none")

    parts: List[str] = []
    for rule in rules:
        if not isinstance(rule, PortForwardingRule):
            continue
        if rule.type == "socks5":
            parts.append(tr("status.port_rule_socks", vm=_extract_port(rule.vm_addr)))
            continue
        parts.append(
            tr(
                "status.port_rule",
                host=_extract_port(rule.host_addr),
                vm=_extract_port(rule.vm_addr),
            )
        )

    return ", ".join(parts) if parts else tr("status.none")


def _format_snapshot_time(snapshot: Path) -> datetime:
    try:
        return datetime.strptime(snapshot.name, "%Y%m%d-%H%M%S")
    except ValueError:
        return datetime.fromtimestamp(snapshot.stat().st_mtime)


def _mount_last_backup(mount: MountConfig) -> tuple[str, Optional[datetime]]:
    snapshots = list_backup_snapshots(mount.backup)
    if not snapshots:
        return tr("status.last_backup_none"), None

    latest = snapshots[-1]
    stamp = _format_snapshot_time(latest)
    return stamp.strftime("%Y-%m-%d %H:%M:%S"), stamp


def _backup_is_active(last_backup: Optional[datetime], interval_minutes: int) -> bool:
    if last_backup is None:
        return False
    delta = datetime.now() - last_backup
    return delta.total_seconds() <= interval_minutes * 2 * 60


def _render_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    if not rows:
        return

    widths = [len(click.unstyle(header)) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(click.unstyle(cell)))

    def _pad(value: str, width: int) -> str:
        plain = click.unstyle(value)
        return value + " " * (width - len(plain))

    header_line = " | ".join(_pad(headers[i], widths[i]) for i in range(len(headers)))
    separator = "-+-".join("-" * widths[i] for i in range(len(headers)))

    click.echo(header_line)
    click.echo(separator)
    for row in rows:
        click.echo(" | ".join(_pad(row[i], widths[i]) for i in range(len(headers))))


def _needs_nvm(binary: str) -> bool:
    return binary in NODE_AGENT_BINARIES


def _check_agent_binary_installed(vm_name: str, binary: str) -> Optional[bool]:
    parts: List[str] = ['export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"']
    if _needs_nvm(binary):
        parts.insert(0, NVM_LOAD_SNIPPET)
    parts.append(f"command -v {shlex.quote(binary)} >/dev/null 2>&1")
    command = " && ".join(parts)

    result = subprocess.run(
        ["multipass", "exec", vm_name, "--", "bash", "-lc", command],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def _match_binary(args: str, binaries: Iterable[str]) -> Optional[str]:
    candidates = list(binaries)

    try:
        tokens = shlex.split(args)
    except ValueError:
        tokens = args.split()

    if tokens:
        command_name = Path(tokens[0]).name
        if command_name in candidates:
            return command_name

    for binary in candidates:
        if re.search(rf"(?<![\\w-]){re.escape(binary)}(?![\\w-])", args):
            return binary
    return None


def _read_process_cwd(vm_name: str, pid: str) -> Optional[str]:
    result = subprocess.run(
        ["multipass", "exec", vm_name, "--", "bash", "-lc", f"readlink -f /proc/{shlex.quote(pid)}/cwd"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    cwd = (result.stdout or "").strip()
    return cwd or None


def _collect_running_agent_processes(vm_name: str, binaries: Sequence[str]) -> Optional[List[Tuple[str, str, Optional[str]]]]:
    if not binaries:
        return []

    result = subprocess.run(
        ["multipass", "exec", vm_name, "--", "ps", "-eo", "pid=,ppid=,args="],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    candidates: List[Tuple[str, str, str]] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        pid, ppid, args = parts
        matched = _match_binary(args, binaries)
        if matched:
            candidates.append((pid, ppid, matched))

    agent_pids = {pid for pid, _ppid, _binary in candidates}

    running: List[Tuple[str, str, Optional[str]]] = []
    for pid, ppid, binary in candidates:
        if ppid in agent_pids:
            continue
        cwd = _read_process_cwd(vm_name, pid)
        running.append((pid, binary, cwd))

    running.sort(key=lambda item: int(item[0]))
    return running


def _vm_state_label(state: str) -> str:
    normalized = state.lower()
    if normalized == "running":
        return click.style(tr("status.vm_state_running"), fg="green")
    if normalized in {"stopped", "suspended"}:
        return click.style(tr("status.vm_state_stopped"), fg="bright_black")
    if normalized == "absent":
        return click.style(tr("status.vm_state_absent"), fg="bright_black")
    return click.style(tr("status.vm_state_unknown", state=state), fg="yellow")


@click.command(name="status", help=tr("status.command_help"))
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
def status_command(config_path: Optional[str], non_interactive: bool) -> None:
    """Show current project status: VMs, mounts, backups, and agents."""

    del non_interactive

    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    click.echo(tr("status.config_path", path=resolved_path))

    try:
        config = load_config(resolved_path)
        vms = load_vms_config(config)
        mounts = load_mounts_config(config)
        agents = load_agents_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    entries, multipass_error = _load_multipass_entries()
    info_entries, info_error = _load_multipass_info_entries()
    inventory_available = multipass_error is None or info_error is None

    if multipass_error and info_error:
        click.echo(click.style(tr("status.multipass_unavailable", error=multipass_error), fg="yellow"))

    portforward_running = _is_portforward_running()

    for vm_name, vm in vms.items():
        click.echo()
        click.echo(click.style(tr("status.vm_header", vm_name=vm_name), bold=True))

        entry = entries.get(vm_name)
        info_entry = info_entries.get(vm_name)
        if entry:
            state = str(entry.get("state", tr("status.vm_state_unknown_raw")))
        elif info_entry:
            state = str(info_entry.get("state", tr("status.vm_state_unknown_raw")))
        elif not inventory_available:
            state = tr("status.vm_state_unknown_raw")
        else:
            state = "absent"
        click.echo(tr("status.vm_state", state=_vm_state_label(state)))

        actual_cpu = _extract_cpu_count(entry, info_entry)
        actual_ram_bytes = _extract_ram_bytes(entry, info_entry)
        actual_disk_bytes = _extract_disk_bytes(entry, info_entry)

        expected_ram_bytes = to_bytes(vm.ram)
        expected_disk_bytes = to_bytes(vm.disk)

        cpu_mismatch = actual_cpu is not None and actual_cpu != str(vm.cpu)
        ram_mismatch = expected_ram_bytes is not None and actual_ram_bytes is not None and expected_ram_bytes != actual_ram_bytes
        disk_mismatch = expected_disk_bytes is not None and actual_disk_bytes is not None and expected_disk_bytes != actual_disk_bytes

        cpu_value = f"{vm.cpu} {tr('status.cpu_unit')}"
        cpu_real = f"{actual_cpu} {tr('status.cpu_unit')}" if actual_cpu is not None else tr("status.size_unknown")
        ram_value = vm.ram
        disk_value = vm.disk

        resources_line = ", ".join(
            [
                f"CPU: {cpu_value}{_format_real_suffix(cpu_real, cpu_mismatch)}",
                f"RAM: {ram_value}{_format_real_suffix(_human_size(actual_ram_bytes), ram_mismatch)}",
                f"Disk: {disk_value}{_format_real_suffix(_human_size(actual_disk_bytes), disk_mismatch)}",
            ]
        )
        click.echo(tr("status.vm_resources", resources=resources_line))

        forwards_text = _format_port_forwarding(vm.port_forwarding)
        click.echo(tr("status.vm_port_forwards", rules=forwards_text))
        if vm.port_forwarding:
            if portforward_running is None:
                pf_state = click.style(tr("status.portforward_unknown"), fg="yellow")
            elif portforward_running:
                pf_state = click.style(tr("status.portforward_running"), fg="green")
            else:
                pf_state = click.style(tr("status.portforward_stopped"), fg="red")
            click.echo(tr("status.vm_portforward_status", status=pf_state))

        vm_mounts = [mount for mount in mounts if mount.vm_name == vm_name]
        click.echo(click.style(tr("status.mounts_header"), bold=True))
        if not vm_mounts:
            click.echo(tr("status.mounts_empty"))
        else:
            rows: List[List[str]] = []
            for mount in vm_mounts:
                last_backup_text, last_backup_dt = _mount_last_backup(mount)
                backups_active = _backup_is_active(last_backup_dt, mount.interval_minutes)
                backups_flag = click.style(tr("status.yes"), fg="green") if backups_active else click.style(tr("status.no"), fg="bright_black")
                rows.append(
                    [
                        str(mount.source),
                        str(mount.target),
                        str(mount.backup),
                        tr("status.interval_minutes", minutes=mount.interval_minutes),
                        tr("status.retention", count=mount.max_backups, method=mount.backup_clean_method),
                        last_backup_text,
                        backups_flag,
                    ]
                )

            _render_table(
                [
                    tr("status.table_source"),
                    tr("status.table_target"),
                    tr("status.table_backup"),
                    tr("status.table_interval"),
                    tr("status.table_retention"),
                    tr("status.table_last_backup"),
                    tr("status.table_backup_running"),
                ],
                rows,
            )

        vm_agents = [agent for agent in agents.values() if agent.vm_name == vm_name]
        click.echo(click.style(tr("status.agents_installed_header"), bold=True))
        if not vm_agents:
            click.echo(tr("status.agents_empty"))
        else:
            vm_running = state.lower() == "running"
            for agent in vm_agents:
                install_state: str
                if not vm_running:
                    install_state = click.style(tr("status.agent_unknown"), fg="bright_black")
                else:
                    installed = _check_agent_binary_installed(vm_name, agent.type)
                    if installed is True:
                        install_state = click.style(tr("status.agent_installed"), fg="green")
                    elif installed is False:
                        install_state = click.style(tr("status.agent_missing"), fg="red")
                    else:
                        install_state = click.style(tr("status.agent_unknown"), fg="yellow")
                click.echo(tr("status.agent_line", name=agent.name, agent_type=agent.type, state=install_state))

        click.echo(click.style(tr("status.agents_running_header"), bold=True))
        if not vm_agents or state.lower() != "running":
            click.echo(tr("status.agents_running_empty"))
            continue

        binary_to_names: Dict[str, List[str]] = {}
        for agent in vm_agents:
            binary_to_names.setdefault(agent.type, []).append(agent.name)

        running_processes = _collect_running_agent_processes(vm_name, list(binary_to_names.keys()))
        if running_processes is None:
            click.echo(click.style(tr("status.agents_running_unknown"), fg="yellow"))
            continue
        if not running_processes:
            click.echo(tr("status.agents_running_empty"))
            continue

        for pid, binary, cwd in running_processes:
            config_names = sorted(binary_to_names.get(binary, [binary]))
            display_cwd = cwd or tr("status.cwd_unknown")
            if len(config_names) == 1:
                click.echo(
                    tr(
                        "status.running_agent_line_single",
                        pid=pid,
                        name=config_names[0],
                        binary=binary,
                        cwd=display_cwd,
                    )
                )
                continue

            names = ", ".join(config_names)
            click.echo(tr("status.running_agent_line", pid=pid, names=names, binary=binary, cwd=display_cwd))
