from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import click
from rich.progress import TaskID

from .ansible_utils import (
    ansible_playbook_command,
    count_playbook_tasks,
    emit_hidden_output_tail,
    run_ansible_playbook,
)
from .debug import debug_log_command, debug_log_result
from .host_tools import multipass_command, ssh_command, ssh_keygen_command
from .i18n import tr
from .progress import ProgressManager
from .vm_bundles import ResolvedBundle, resolve_bundles
from .vm import MultipassError

_VM_SSH_USER = "ubuntu"
_VM_SSH_COMMON_ARGS = " ".join(
    [
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=4",
    ]
)


def vm_ssh_ansible_vars(vm_name: str, vm_host: str, private_key: Path) -> Dict[str, str]:
    return {
        "vm_name": vm_name,
        "ansible_host": vm_host,
        "ansible_connection": "ssh",
        "ansible_user": _VM_SSH_USER,
        "ansible_ssh_private_key_file": str(private_key.expanduser().resolve()),
        "ansible_ssh_executable": ssh_command(),
        "ansible_ssh_common_args": _VM_SSH_COMMON_ARGS,
    }


def _run_multipass(
    command: list[str],
    description: str,
    capture_output: bool = True,
    progress: Optional[ProgressManager] = None,
    *,
    debug: bool = False,
) -> subprocess.CompletedProcess[str]:
    message = tr("prepare.command_running", description=description, command=" ".join(shlex.quote(part) for part in command))
    if progress and debug:
        progress.print(message)
    else:
        if debug:
            click.echo(message)
    debug_log_command(command)
    result = subprocess.run(command, check=False, capture_output=capture_output, text=True)
    debug_log_result(result)
    return result


def _derive_public_key(private_key: Path) -> str:
    result = subprocess.run(
        [ssh_keygen_command(), "-y", "-f", str(private_key)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def ensure_host_ssh_keypair(*, ssh_dir: Optional[Path] = None, verbose: bool = True) -> Tuple[Path, Path]:
    ssh_dir = (ssh_dir or (Path.home() / ".config" / "agsekit" / "ssh")).expanduser().resolve()
    private_key = ssh_dir / "id_rsa"
    public_key = ssh_dir / "id_rsa.pub"
    ssh_dir.mkdir(parents=True, exist_ok=True)

    if private_key.exists():
        expected_public_key = _derive_public_key(private_key)
        existing_public_key = public_key.read_text(encoding="utf-8").strip() if public_key.exists() else None

        if existing_public_key == expected_public_key:
            if verbose:
                click.echo(tr("prepare.ssh_keypair_exists", path=ssh_dir))
            return private_key, public_key

        if not public_key.exists():
            if verbose:
                click.echo(tr("prepare.ssh_public_missing", path=ssh_dir))
        public_key.write_text(f"{expected_public_key}\n", encoding="utf-8")
    else:
        if verbose:
            click.echo(tr("prepare.ssh_generating", path=ssh_dir))
        subprocess.run(
            ["ssh-keygen", "-t", "rsa", "-b", "4096", "-N", "", "-f", str(private_key)],
            check=True,
        )

    os.chmod(private_key, 0o600)
    if public_key.exists():
        os.chmod(public_key, 0o644)

    if verbose:
        click.echo(tr("prepare.ssh_ready", path=ssh_dir))
    return private_key, public_key


def _run_ansible_with_progress(
    command: list[str],
    *,
    playbook: Path,
    progress: Optional[ProgressManager],
    label: str,
) -> subprocess.CompletedProcess[str]:
    if not progress:
        return run_ansible_playbook(command, playbook_path=playbook)
    total = count_playbook_tasks(playbook)
    task_id = progress.add_task(label, total=max(total, 1))

    def _handle_progress(current: int, total_tasks: int, task_name: str) -> None:
        effective_total = total_tasks if total_tasks > 0 else total
        progress.update(task_id, description=f"{label}: {task_name}", completed=min(current, effective_total))

    try:
        return run_ansible_playbook(
            command,
            playbook_path=playbook,
            progress_handler=_handle_progress,
            progress_output=progress.print,
        )
    finally:
        progress.remove_task(task_id)


def _report_hidden_output_tail(
    result: subprocess.CompletedProcess[str],
    progress: Optional[ProgressManager],
) -> None:
    if progress and hasattr(progress, "halt"):
        progress.halt()
    emit_hidden_output_tail(result, err=True)


def _ensure_vm_packages(
    vm_name: str,
    vm_host: str,
    private_key: Path,
    progress: Optional[ProgressManager] = None,
    step_task_id: Optional[TaskID] = None,
) -> None:
    if progress and step_task_id is not None:
        progress.update(step_task_id, description=tr("progress.prepare_step_packages"))
    else:
        click.echo(tr("prepare.installing_packages", vm_name=vm_name))
    playbook = Path(__file__).resolve().parent / "ansible" / "vm_packages.yml"
    command = [
        *ansible_playbook_command(),
        "-i",
        "localhost,",
        "-e",
        json.dumps(vm_ssh_ansible_vars(vm_name, vm_host, private_key), ensure_ascii=False),
        str(playbook),
    ]
    if progress:
        result = _run_ansible_with_progress(
            command,
            playbook=playbook,
            progress=progress,
            label=tr("progress.ansible_task", stage=tr("progress.prepare_step_packages")),
        )
    else:
        result = run_ansible_playbook(
            command,
            playbook_path=playbook,
        )
    if result.returncode != 0:
        _report_hidden_output_tail(result, progress)
        raise MultipassError(tr("prepare.install_failed", vm_name=vm_name))
    if progress and step_task_id is not None:
        progress.advance(step_task_id)


def _ensure_vm_ssh_access(
    vm_name: str,
    public_key: Path,
    vm_known_hosts: Iterable[str],
    progress: Optional[ProgressManager] = None,
    step_task_id: Optional[TaskID] = None,
) -> None:
    if progress:
        if step_task_id is not None:
            progress.update(step_task_id, description=tr("progress.prepare_step_ssh"))
    else:
        click.echo(tr("prepare.syncing_keys", vm_name=vm_name))
        click.echo(tr("prepare.ensure_authorized_keys", vm_name=vm_name))
        click.echo(tr("prepare.ensure_known_hosts", vm_name=vm_name))

    playbook = Path(__file__).resolve().parent / "ansible" / "vm_ssh.yml"
    public_key_line = public_key.read_text(encoding="utf-8").strip()
    known_hosts = [host.strip() for host in vm_known_hosts if host and host.strip()]
    extra_vars = {
        "vm_name": vm_name,
        "host_public_key": public_key_line,
        "vm_known_hosts": known_hosts,
    }
    command = [
        *ansible_playbook_command(),
        "-i",
        "localhost,",
        "-e",
        json.dumps(extra_vars, ensure_ascii=False),
        str(playbook),
    ]
    if progress:
        result = _run_ansible_with_progress(
            command,
            playbook=playbook,
            progress=progress,
            label=tr("progress.ansible_task", stage=tr("progress.prepare_step_ssh")),
        )
    else:
        result = run_ansible_playbook(
            command,
            playbook_path=playbook,
        )
    if result.returncode != 0:
        _report_hidden_output_tail(result, progress)
        raise MultipassError(tr("prepare.ssh_sync_failed", vm_name=vm_name))
    if progress and step_task_id is not None:
        progress.advance(step_task_id)


def _install_vm_bundles(
    vm_name: str,
    vm_host: str,
    private_key: Path,
    bundles: List[ResolvedBundle],
    progress: Optional[ProgressManager] = None,
    step_task_id: Optional[TaskID] = None,
) -> None:
    if not bundles:
        if progress and step_task_id is not None:
            progress.update(step_task_id, description=tr("progress.prepare_step_bundles_none"))
            progress.advance(step_task_id)
        else:
            click.echo(tr("prepare.install_bundles_none", vm_name=vm_name))
        return

    bundle_list = ", ".join(bundle.raw for bundle in bundles)
    bundle_task_id: Optional[TaskID] = None
    if progress and step_task_id is not None:
        progress.update(step_task_id, description=tr("progress.prepare_step_bundles"))
        bundle_task_id = progress.add_task(tr("progress.bundles_title"), total=len(bundles))
    else:
        click.echo(tr("prepare.install_bundles_start", vm_name=vm_name, bundles=bundle_list))

    for bundle in bundles:
        if progress and bundle_task_id is not None:
            progress.update(bundle_task_id, description=tr("progress.bundle_step", bundle=bundle.raw))
        else:
            click.echo(tr("prepare.install_bundle_running", vm_name=vm_name, bundle=bundle.raw))
        playbook = bundle.playbook
        command = [
            *ansible_playbook_command(),
            "-i",
            "localhost,",
            "-e",
            json.dumps(vm_ssh_ansible_vars(vm_name, vm_host, private_key), ensure_ascii=False),
        ]
        if bundle.version:
            command.extend(["-e", f"bundle_version={bundle.version}"])
        command.append(str(playbook))
        if progress:
            install_result = _run_ansible_with_progress(
                command,
                playbook=playbook,
                progress=progress,
                label=tr("progress.ansible_task", stage=tr("progress.bundle_step", bundle=bundle.raw)),
            )
        else:
            install_result = run_ansible_playbook(
                command,
                playbook_path=playbook,
            )
        if install_result.returncode != 0:
            _report_hidden_output_tail(install_result, progress)
            raise MultipassError(tr("prepare.install_bundle_failed", vm_name=vm_name, bundle=bundle.raw))
        if progress and bundle_task_id is not None:
            progress.advance(bundle_task_id)
    if progress and step_task_id is not None:
        progress.advance(step_task_id)


def _fetch_vm_ips(
    vm_name: str,
    progress: Optional[ProgressManager] = None,
    *,
    debug: bool = False,
) -> List[str]:
    result = _run_multipass(
        [multipass_command(), "info", vm_name, "--format", "json"],
        tr("prepare.fetching_vm_info", vm_name=vm_name),
        progress=progress,
        debug=debug,
    )
    if result.returncode != 0:
        raise MultipassError(tr("prepare.vm_info_failed", vm_name=vm_name))

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MultipassError(tr("prepare.vm_info_parse_failed", vm_name=vm_name)) from exc

    info = data.get("info", {}) if isinstance(data, dict) else {}
    vm_info = info.get(vm_name, {}) if isinstance(info, dict) else {}
    ipv4 = vm_info.get("ipv4") or vm_info.get("IPv4") or []
    if isinstance(ipv4, str):
        return [ipv4] if ipv4 else []
    if isinstance(ipv4, list):
        return [item for item in ipv4 if isinstance(item, str) and item]
    return []


def prepare_vm(
    vm_name: str,
    private_key: Path,
    public_key: Path,
    bundles: Optional[List[str]] = None,
    progress: Optional[ProgressManager] = None,
    step_task_id: Optional[TaskID] = None,
    *,
    debug: bool = False,
) -> None:
    if progress and step_task_id is not None:
        progress.update(step_task_id, description=tr("progress.prepare_step_start", vm_name=vm_name))
    else:
        click.echo(tr("prepare.preparing_vm", vm_name=vm_name))
    _run_multipass(
        [multipass_command(), "start", vm_name],
        tr("prepare.starting_vm", vm_name=vm_name),
        progress=progress,
        debug=debug,
    )
    if progress and step_task_id is not None:
        progress.advance(step_task_id)
        progress.update(step_task_id, description=tr("progress.prepare_step_info", vm_name=vm_name))
    hosts = _fetch_vm_ips(vm_name, progress=progress, debug=debug)
    if not hosts:
        raise MultipassError(tr("prepare.no_vm_ips", vm_name=vm_name))
    if progress and step_task_id is not None:
        progress.advance(step_task_id)
    _ensure_vm_ssh_access(vm_name, public_key, [vm_name, *hosts], progress, step_task_id)
    vm_host = hosts[0]
    _ensure_vm_packages(vm_name, vm_host, private_key, progress, step_task_id)
    resolved_bundles = resolve_bundles(bundles or [], vm_name) if bundles else []
    _install_vm_bundles(vm_name, vm_host, private_key, resolved_bundles, progress, step_task_id)
    prepared_message = tr("prepare.prepared_vm", vm_name=vm_name)
    if progress:
        if debug:
            progress.print(prepared_message)
    else:
        click.echo(prepared_message)
