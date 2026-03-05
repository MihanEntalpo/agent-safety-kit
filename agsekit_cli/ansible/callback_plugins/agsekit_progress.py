from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any, Optional

from ansible.plugins.callback import CallbackBase
from ansible.utils.display import Display


display = Display()


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "agsekit_progress"

    def __init__(self) -> None:
        super().__init__()
        self._current = 0
        self._total = self._int_env("AGSEKIT_ANSIBLE_TOTAL_TASKS", default=0)
        self._bar_width = self._int_env("AGSEKIT_ANSIBLE_PROGRESS_WIDTH", default=24)
        self._spinner_frames = ("|", "/", "-", "\\")
        self._spinner_index = 0
        self._active_task = ""
        self._interactive = sys.stdout.isatty()
        self._rendered = False
        self._spinner_stop = threading.Event()
        self._spinner_thread: Optional[threading.Thread] = None
        self._render_lock = threading.Lock()

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

    def _format_bar(self) -> str:
        if self._total <= 0:
            filled = min(self._current, self._bar_width)
        else:
            ratio = min(max(self._current / max(self._total, 1), 0.0), 1.0)
            filled = int(round(ratio * self._bar_width))
        empty = max(self._bar_width - filled, 0)
        return "[" + ("#" * filled) + ("_" * empty) + "]"

    @staticmethod
    def _task_name(task: Any) -> str:
        if hasattr(task, "get_name"):
            name = str(task.get_name() or "").strip()
            if name:
                return name
        return "unnamed task"

    def _emit_line(self, line: str) -> None:
        if self._interactive:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
            return
        display.display(line)

    def _render_progress(self, spinner: str) -> None:
        total = self._total if self._total > 0 else self._current
        task_line = f"{spinner} {self._current}/{total} {self._active_task}".rstrip()
        bar_line = self._format_bar()

        if not self._interactive:
            self._emit_line(task_line)
            self._emit_line(bar_line)
            return

        with self._render_lock:
            if self._rendered:
                # Move cursor to the start of the previous 2-line progress block.
                sys.stdout.write("\x1b[2F")

            sys.stdout.write("\x1b[2K" + task_line + "\n")
            sys.stdout.write("\x1b[2K" + bar_line + "\n")
            sys.stdout.flush()
            self._rendered = True

    def _clear_rendered_progress(self) -> None:
        if not self._interactive or not self._rendered:
            return

        with self._render_lock:
            # Move to the first line of the progress block and clear two lines.
            sys.stdout.write("\x1b[2F")
            sys.stdout.write("\x1b[2K\n")
            sys.stdout.write("\x1b[2K")
            # Return cursor to the first cleared line, so the next output overwrites it.
            sys.stdout.write("\x1b[1F\r")
            sys.stdout.flush()
            self._rendered = False

    def _spinner_loop(self) -> None:
        while not self._spinner_stop.is_set():
            frame = self._spinner_frames[self._spinner_index % len(self._spinner_frames)]
            self._spinner_index += 1
            self._render_progress(frame)
            time.sleep(0.1)

    def _start_spinner(self) -> None:
        self._stop_spinner()
        if not self._interactive:
            self._render_progress(self._spinner_frames[0])
            return
        self._spinner_stop.clear()
        self._spinner_thread = threading.Thread(target=self._spinner_loop, daemon=True)
        self._spinner_thread.start()

    def _stop_spinner(self, status: Optional[str] = None) -> None:
        if self._spinner_thread is not None:
            self._spinner_stop.set()
            self._spinner_thread.join(timeout=0.3)
            self._spinner_thread = None
        self._spinner_stop.clear()

        if status:
            self._render_progress(status)

    def v2_playbook_on_start(self, _playbook: Any) -> None:
        header = os.environ.get("AGSEKIT_ANSIBLE_HEADER", "").strip()
        if header:
            self._emit_line(header)

    def v2_playbook_on_task_start(self, task: Any, is_conditional: bool) -> None:
        del is_conditional
        self._stop_spinner()
        self._current += 1
        if self._total > 0 and self._current > self._total:
            self._total = self._current
        self._active_task = self._task_name(task)
        self._start_spinner()

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
        self._stop_spinner("X")
        self._emit_line(self._failure_line(result))

    def v2_runner_on_unreachable(self, result: Any) -> None:
        self._stop_spinner("X")
        self._emit_line(self._failure_line(result))

    def v2_runner_on_ok(self, result: Any) -> None:
        del result
        self._stop_spinner("o")

    def v2_runner_on_skipped(self, result: Any) -> None:
        del result
        self._stop_spinner("s")

    def v2_playbook_on_stats(self, stats: Any) -> None:
        has_errors = False
        if stats is not None and hasattr(stats, "processed"):
            for host in getattr(stats, "processed", {}):
                summary = stats.summarize(host)
                if summary.get("failures", 0) or summary.get("unreachable", 0):
                    has_errors = True
                    break

        self._stop_spinner()
        if not has_errors:
            self._clear_rendered_progress()
