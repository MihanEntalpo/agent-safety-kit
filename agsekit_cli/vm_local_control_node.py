from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, Optional

import click
import yaml

from .debug import debug_log_command, debug_log_result
from .host_tools import multipass_command
from .i18n import tr
from .progress import ProgressManager
from .vm import MultipassError

CONTROL_NODE_ROOT = "/home/ubuntu/.local/share/agsekit/control-node"
CONTROL_NODE_PROJECT = f"{CONTROL_NODE_ROOT}/project"
CONTROL_NODE_VENV = f"{CONTROL_NODE_ROOT}/venv"


class VmLocalControlNode:
    def __init__(self, vm_name: str) -> None:
        self.vm_name = vm_name
        self.package_root = Path(__file__).resolve().parent

    def ensure_ready(
        self,
        *,
        progress: Optional[ProgressManager] = None,
        debug: bool = False,
    ) -> None:
        self._upload_payload(progress=progress, debug=debug)
        self._ensure_venv_and_ansible(progress=progress, debug=debug)

    def playbook_path_in_vm(self, playbook_path: Path) -> str:
        relative = playbook_path.resolve().relative_to(self.package_root)
        return f"{CONTROL_NODE_PROJECT}/{relative.as_posix()}"

    def _run_multipass(
        self,
        command: list[str],
        description: str,
        *,
        capture_output: bool = True,
        progress: Optional[ProgressManager] = None,
        debug: bool = False,
    ) -> subprocess.CompletedProcess[str]:
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
        result = subprocess.run(command, check=False, capture_output=capture_output, text=True)
        debug_log_result(result)
        return result

    def _upload_payload(self, *, progress: Optional[ProgressManager], debug: bool) -> None:
        with tempfile.TemporaryDirectory(prefix="agsekit-control-node-") as tmp_dir_raw:
            tmp_dir = Path(tmp_dir_raw)
            project_dir = tmp_dir / "project"
            self._build_payload_tree(project_dir)
            archive_path = tmp_dir / "project.tgz"
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(project_dir, arcname="project")

            remote_archive = f"{self.vm_name}:/tmp/agsekit-control-node-project.tgz"
            transfer_command = [multipass_command(), "transfer", str(archive_path), remote_archive]
            transfer_result = self._run_multipass(
                transfer_command,
                tr("prepare.control_node_transfer", vm_name=self.vm_name),
                progress=progress,
                debug=debug,
            )
            if transfer_result.returncode != 0:
                raise MultipassError(tr("prepare.control_node_transfer_failed", vm_name=self.vm_name))

            extract_script = "\n".join(
                [
                    "set -eu",
                    f"mkdir -p {shlex.quote(CONTROL_NODE_ROOT)}",
                    f"rm -rf {shlex.quote(CONTROL_NODE_PROJECT)}",
                    f"tar -xzf /tmp/agsekit-control-node-project.tgz -C {shlex.quote(CONTROL_NODE_ROOT)}",
                    "rm -f /tmp/agsekit-control-node-project.tgz",
                ]
            )
            extract_result = self._run_multipass(
                [multipass_command(), "exec", self.vm_name, "--", "bash", "-lc", extract_script],
                tr("prepare.control_node_extract", vm_name=self.vm_name),
                progress=progress,
                debug=debug,
            )
            if extract_result.returncode != 0:
                raise MultipassError(tr("prepare.control_node_extract_failed", vm_name=self.vm_name))

    def _ensure_venv_and_ansible(self, *, progress: Optional[ProgressManager], debug: bool) -> None:
        script = "\n".join(
            [
                "set -eu",
                f"root={shlex.quote(CONTROL_NODE_ROOT)}",
                f"venv={shlex.quote(CONTROL_NODE_VENV)}",
                'if [ ! -x "$venv/bin/python" ]; then',
                '  python3 -m venv "$venv" >/dev/null 2>&1 || {',
                '    sudo apt-get update',
                '    sudo apt-get install -y python3-venv',
                '    python3 -m venv "$venv"',
                '  }',
                'fi',
                'if ! "$venv/bin/python" -c "import ansible" >/dev/null 2>&1; then',
                '  "$venv/bin/python" -m pip install --upgrade pip',
                '  "$venv/bin/python" -m pip install "ansible-core>=2.16,<2.19"',
                'fi',
            ]
        )
        result = self._run_multipass(
            [multipass_command(), "exec", self.vm_name, "--", "bash", "-lc", script],
            tr("prepare.control_node_setup", vm_name=self.vm_name),
            progress=progress,
            debug=debug,
        )
        if result.returncode != 0:
            raise MultipassError(tr("prepare.control_node_setup_failed", vm_name=self.vm_name))

    def _build_payload_tree(self, project_dir: Path) -> None:
        ansible_src = self.package_root / "ansible"
        agent_scripts_src = self.package_root / "agent_scripts"
        shutil.copytree(ansible_src, project_dir / "ansible")
        shutil.copytree(agent_scripts_src, project_dir / "agent_scripts")
        for script_name in ("run_with_http_proxy.sh", "run_with_proxychains.sh", "run_agent.sh"):
            shutil.copy2(self.package_root / script_name, project_dir / script_name)

        for playbook_path in sorted((project_dir / "ansible").rglob("*.yml")):
            self._rewrite_playbook_for_local_control_node(playbook_path)

    def _rewrite_playbook_for_local_control_node(self, playbook_path: Path) -> None:
        try:
            payload = yaml.safe_load(playbook_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(payload, list):
            return

        rewritten = list(payload)
        if rewritten and self._is_multipass_registration_play(rewritten[0]):
            rewritten = rewritten[1:]
        if not rewritten:
            return

        changed = False
        for play in rewritten:
            if not isinstance(play, dict):
                continue
            hosts = str(play.get("hosts", "")).strip()
            if hosts == "{{ vm_name }}":
                play["hosts"] = "localhost"
                play["connection"] = "local"
                vars_block = play.get("vars")
                if not isinstance(vars_block, dict):
                    vars_block = {}
                    play["vars"] = vars_block
                vars_block.setdefault("ansible_python_interpreter", "/usr/bin/python3")
                changed = True

        if not changed and rewritten == payload:
            return
        playbook_path.write_text(yaml.safe_dump(rewritten, sort_keys=False), encoding="utf-8")

    @staticmethod
    def _is_multipass_registration_play(play: object) -> bool:
        if not isinstance(play, dict):
            return False
        tasks = play.get("tasks")
        if not isinstance(tasks, list) or len(tasks) != 1:
            return False
        task = tasks[0]
        if not isinstance(task, dict):
            return False
        add_host = task.get("ansible.builtin.add_host")
        return isinstance(add_host, dict) and add_host.get("ansible_connection") == "agsekit_multipass"



def vm_local_ansible_vars(vm_name: str, extra_vars: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "vm_name": vm_name,
        "ansible_python_interpreter": "/usr/bin/python3",
    }
    if extra_vars:
        payload.update(extra_vars)
    return payload



def run_vm_local_playbook(
    vm_name: str,
    playbook_path: Path,
    *,
    extra_vars: Optional[Dict[str, object]] = None,
    debug: bool = False,
    progress: Optional[ProgressManager] = None,
) -> subprocess.CompletedProcess[str]:
    control_node = VmLocalControlNode(vm_name)
    command: list[str] = [
        multipass_command(),
        "exec",
        vm_name,
        "--",
        "bash",
        "-lc",
        " ".join(
            [
                "export ANSIBLE_HOST_KEY_CHECKING=False",
                "&&",
                shlex.quote(f"{CONTROL_NODE_VENV}/bin/python"),
                "-m",
                "ansible.cli.playbook",
                "-i",
                shlex.quote("localhost,"),
                "-e",
                shlex.quote(json.dumps(vm_local_ansible_vars(vm_name, extra_vars), ensure_ascii=False)),
                *( ["-vvv"] if debug else [] ),
                shlex.quote(control_node.playbook_path_in_vm(playbook_path)),
            ]
        ),
    ]
    message = tr(
        "prepare.command_running",
        description=tr("prepare.control_node_playbook", vm_name=vm_name, playbook=playbook_path.name),
        command=" ".join(shlex.quote(part) for part in command),
    )
    if progress and debug:
        progress.print(message)
    elif debug:
        click.echo(message)
    debug_log_command(command)
    result = subprocess.run(command, check=False, capture_output=not debug, text=True)
    debug_log_result(result)
    return result
