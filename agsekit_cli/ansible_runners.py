from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional, Sequence

from .ansible_utils import count_playbook_tasks, run_ansible_playbook
from .debug import is_debug_enabled
from .progress import ProgressManager
from .vm_local_control_node import VmLocalControlNode, run_vm_local_playbook


class HostAnsibleRunner:
    def run_playbook(
        self,
        command: Sequence[str],
        *,
        playbook_path: Path,
        progress: Optional[ProgressManager] = None,
        label: Optional[str] = None,
    ):
        if not progress or not label or is_debug_enabled():
            return run_ansible_playbook(command, playbook_path=playbook_path)

        total = count_playbook_tasks(playbook_path)
        task_id = progress.add_task(label, total=max(total, 1))

        def _handle_progress(current: int, total_tasks: int, task_name: str) -> None:
            effective_total = total_tasks if total_tasks > 0 else total
            progress.update(task_id, description=f"{label}: {task_name}", completed=min(current, effective_total))

        try:
            return run_ansible_playbook(
                command,
                playbook_path=playbook_path,
                progress_handler=_handle_progress,
                progress_output=progress.print,
            )
        finally:
            progress.remove_task(task_id)


class VmLocalAnsibleRunner:
    def __init__(self, vm_name: str) -> None:
        self.vm_name = vm_name
        self.control_node = VmLocalControlNode(vm_name)

    def ensure_ready(self, *, progress: Optional[ProgressManager] = None, debug: bool = False) -> None:
        self.control_node.ensure_ready(progress=progress, debug=debug)

    def run_playbook(
        self,
        playbook_path: Path,
        *,
        extra_vars: Optional[Dict[str, object]] = None,
        progress: Optional[ProgressManager] = None,
        debug: bool = False,
    ):
        return run_vm_local_playbook(
            self.vm_name,
            playbook_path,
            extra_vars=extra_vars,
            debug=debug,
            progress=progress,
        )
