from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional

import click

from .debug import debug_log_command, debug_log_result
from .host_tools import multipass_command, ssh_keygen_command
from .i18n import tr
from .progress import ProgressManager
from .vm import MultipassError


def _run_multipass_exec(
    vm_name: str,
    script: str,
    description: str,
    *,
    progress: Optional[ProgressManager] = None,
    debug: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [multipass_command(), "exec", vm_name, "--", "bash", "-lc", script]
    message = tr(
        "prepare.command_running",
        description=description,
        command=" ".join(shlex.quote(part) for part in command),
    )
    if progress and debug:
        progress.print(message)
    elif debug:
        click.echo(message)
    debug_log_command(command)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    debug_log_result(result)
    return result


def ensure_vm_authorized_keys_with_multipass(
    vm_name: str,
    public_key_line: str,
    *,
    progress: Optional[ProgressManager] = None,
    debug: bool = False,
) -> None:
    script = "\n".join(
        [
            "set -eu",
            'install -d -m 700 "$HOME/.ssh"',
            'touch "$HOME/.ssh/authorized_keys"',
            'chmod 600 "$HOME/.ssh/authorized_keys"',
            f"key={shlex.quote(public_key_line)}",
            'grep -qxF "$key" "$HOME/.ssh/authorized_keys" || printf "%s\\n" "$key" >> "$HOME/.ssh/authorized_keys"',
        ]
    )
    result = _run_multipass_exec(
        vm_name,
        script,
        tr("prepare.ensure_authorized_keys_command", vm_name=vm_name),
        progress=progress,
        debug=debug,
    )
    if result.returncode != 0:
        raise MultipassError(tr("prepare.authorized_keys_failed", vm_name=vm_name))



def fetch_vm_host_public_keys_with_multipass(
    vm_name: str,
    *,
    progress: Optional[ProgressManager] = None,
    debug: bool = False,
) -> List[str]:
    script = "\n".join(
        [
            "set -eu",
            'for path in /etc/ssh/ssh_host_*_key.pub; do',
            '  [ -f "$path" ] || continue',
            '  cat "$path"',
            'done',
        ]
    )
    result = _run_multipass_exec(
        vm_name,
        script,
        tr("prepare.ensure_known_hosts", vm_name=vm_name),
        progress=progress,
        debug=debug,
    )
    if result.returncode != 0:
        raise MultipassError(tr("prepare.known_hosts_failed", host=vm_name))
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]



def sync_vm_known_hosts(hosts: Iterable[str], host_public_keys: Iterable[str]) -> None:
    normalized_hosts = [host.strip() for host in hosts if host and host.strip()]
    normalized_keys = [line.strip() for line in host_public_keys if line and line.strip()]
    if not normalized_hosts or not normalized_keys:
        return

    known_hosts_path = Path.home() / ".ssh" / "known_hosts"
    known_hosts_path.parent.mkdir(parents=True, exist_ok=True)
    if not known_hosts_path.exists():
        known_hosts_path.touch()

    ssh_keygen = ssh_keygen_command()
    for host in normalized_hosts:
        subprocess.run(
            [ssh_keygen, "-R", host, "-f", str(known_hosts_path)],
            check=False,
            capture_output=True,
            text=True,
        )

    with known_hosts_path.open("a", encoding="utf-8") as handle:
        for host in normalized_hosts:
            for key_line in normalized_keys:
                handle.write(f"{host} {key_line}\n")



def bootstrap_vm_ssh_with_multipass(
    vm_name: str,
    public_key: Path,
    vm_known_hosts: Iterable[str],
    *,
    progress: Optional[ProgressManager] = None,
    debug: bool = False,
) -> None:
    public_key_line = public_key.read_text(encoding="utf-8").strip()
    ensure_vm_authorized_keys_with_multipass(
        vm_name,
        public_key_line,
        progress=progress,
        debug=debug,
    )
    host_public_keys = fetch_vm_host_public_keys_with_multipass(
        vm_name,
        progress=progress,
        debug=debug,
    )
    sync_vm_known_hosts(vm_known_hosts, host_public_keys)
