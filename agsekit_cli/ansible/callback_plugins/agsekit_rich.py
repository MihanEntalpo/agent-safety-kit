from __future__ import annotations

import os
import sys
from typing import Any, Optional

from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "agsekit_rich"

    def __init__(self) -> None:
        super().__init__()
        self._current = 0
        self._total = self._int_env("AGSEKIT_ANSIBLE_TOTAL_TASKS", default=0)

    @staticmethod
    def _int_env(name: str, *, default: int) -> int:
        value = os.environ.get(name)
        if value is None:
            return default
        try:
            parsed = int(value)
        except ValueError:
            return default
        return parsed if parsed > 0 else default

    @staticmethod
    def _task_name(task: Any) -> str:
        if hasattr(task, "get_name"):
            name = str(task.get_name() or "").strip()
            if name:
                return name
        return "unnamed task"

    def _emit(self, line: str) -> None:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    def v2_playbook_on_task_start(self, task: Any, is_conditional: bool) -> None:
        del is_conditional
        self._current += 1
        total = self._total if self._total > 0 else self._current
        task_name = self._task_name(task)
        self._emit(f"AGSEKIT_PROGRESS {self._current} {total} {task_name}")

    def _failure_line(self, result: Any) -> str:
        task = getattr(result, "_task", None)
        host = getattr(result, "_host", None)
        result_payload: Optional[dict[str, Any]]
        if isinstance(getattr(result, "_result", None), dict):
            result_payload = result._result
        else:
            result_payload = None

        task_name = self._task_name(task)
        host_name = host.get_name() if hasattr(host, "get_name") else "unknown host"
        message = result_payload.get("msg") if isinstance(result_payload, dict) else None
        if isinstance(message, str) and message.strip():
            return f"FAILED {task_name} ({host_name}): {message.strip()}"
        return f"FAILED {task_name} ({host_name})"

    def v2_runner_on_failed(self, result: Any, ignore_errors: bool = False) -> None:
        del ignore_errors
        self._emit(f"AGSEKIT_FAILED {self._failure_line(result)}")

    def v2_runner_on_unreachable(self, result: Any) -> None:
        self._emit(f"AGSEKIT_FAILED {self._failure_line(result)}")
