from __future__ import annotations

import os
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Any, Callable, Deque, Iterable, Optional, Sequence

import click
import yaml

from .debug import debug_log_command, debug_log_result, is_debug_enabled
from .i18n import tr

_ANSIBLE_PROGRESS_CALLBACK = "agsekit_progress"
_ANSIBLE_PROGRESS_TOTAL_ENV = "AGSEKIT_ANSIBLE_TOTAL_TASKS"
_ANSIBLE_PROGRESS_HEADER_ENV = "AGSEKIT_ANSIBLE_HEADER"
_ANSIBLE_HIDDEN_OUTPUT_TAIL_LINES = 10


class AnsiblePlaybookResult(subprocess.CompletedProcess[str]):
    def __init__(
        self,
        args: Sequence[str],
        returncode: int,
        *,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        hidden_output_tail: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(args=args, returncode=returncode, stdout=stdout, stderr=stderr)
        self.hidden_output_tail = tuple(hidden_output_tail or ())


def get_hidden_output_tail(
    result: subprocess.CompletedProcess[str],
    *,
    max_lines: int = _ANSIBLE_HIDDEN_OUTPUT_TAIL_LINES,
) -> tuple[str, ...]:
    raw_lines = getattr(result, "hidden_output_tail", ())
    if not isinstance(raw_lines, (list, tuple)):
        return ()
    normalized = [str(line).rstrip() for line in raw_lines if str(line).strip()]
    if max_lines <= 0:
        return tuple(normalized)
    return tuple(normalized[-max_lines:])


def emit_hidden_output_tail(
    result: subprocess.CompletedProcess[str],
    *,
    err: bool = False,
    max_lines: int = _ANSIBLE_HIDDEN_OUTPUT_TAIL_LINES,
    print_fn: Optional[Callable[[str], None]] = None,
) -> None:
    hidden_output_tail = get_hidden_output_tail(result, max_lines=max_lines)
    if not hidden_output_tail:
        return
    message = tr("ansible.hidden_output_tail_label", output="\n".join(hidden_output_tail))
    if print_fn is not None:
        print_fn(message)
        return
    click.echo(message, err=err)


def _append_output_tail_line(tail: Deque[str], line: str) -> None:
    stripped = line.rstrip()
    if stripped:
        tail.append(stripped)


def ansible_playbook_command() -> list[str]:
    return [sys.executable, "-m", "ansible.cli.playbook"]


def _ansible_plugins_dir(kind: str) -> Path:
    return Path(__file__).resolve().parent / "ansible" / kind


def _merge_plugin_paths(existing: Optional[str], custom: Path) -> str:
    if not existing:
        return str(custom)
    paths = [entry for entry in existing.split(os.pathsep) if entry]
    if str(custom) in paths:
        return existing
    return os.pathsep.join([str(custom), *paths])


def _resolve_include_path(raw_value: Any, current_dir: Path) -> Optional[Path]:
    include_value = raw_value
    if isinstance(raw_value, dict):
        include_value = raw_value.get("file")

    if not isinstance(include_value, str):
        return None

    candidate = include_value.strip()
    if not candidate:
        return None

    candidate = candidate.replace("{{ playbook_dir }}", str(current_dir))
    if "{{" in candidate or "}}" in candidate:
        return None

    include_path = Path(candidate)
    if not include_path.is_absolute():
        include_path = current_dir / include_path
    return include_path.resolve()


def _extract_include_path(task: dict[str, Any], current_dir: Path) -> Optional[Path]:
    include_keys = (
        "include_tasks",
        "import_tasks",
        "ansible.builtin.include_tasks",
        "ansible.builtin.import_tasks",
    )
    for key in include_keys:
        if key not in task:
            continue
        resolved = _resolve_include_path(task.get(key), current_dir)
        if resolved is not None:
            return resolved
    return None


def _count_tasks_in_file(path: Path, stack: set[Path]) -> int:
    resolved = path.resolve()
    if not resolved.exists() or resolved in stack:
        return 0

    stack.add(resolved)
    try:
        payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        return _count_yaml_tasks(payload, resolved.parent, stack)
    except Exception:
        return 0
    finally:
        stack.remove(resolved)


def _count_task_list(tasks: Iterable[Any], current_dir: Path, stack: set[Path]) -> int:
    total = 0
    for entry in tasks:
        if not isinstance(entry, dict):
            continue

        block = entry.get("block")
        if isinstance(block, list):
            total += _count_task_list(block, current_dir, stack)
            rescue = entry.get("rescue")
            always = entry.get("always")
            if isinstance(rescue, list):
                total += _count_task_list(rescue, current_dir, stack)
            if isinstance(always, list):
                total += _count_task_list(always, current_dir, stack)
            continue

        include_path = _extract_include_path(entry, current_dir)
        if include_path is not None:
            total += 1
            total += _count_tasks_in_file(include_path, stack)
            continue

        total += 1
    return total


def _count_play_tasks(play: dict[str, Any], current_dir: Path, stack: set[Path]) -> int:
    total = 0
    for section in ("pre_tasks", "tasks", "post_tasks"):
        entries = play.get(section)
        if isinstance(entries, list):
            total += _count_task_list(entries, current_dir, stack)
    return total


def _count_yaml_tasks(payload: Any, current_dir: Path, stack: set[Path]) -> int:
    if isinstance(payload, list):
        if payload and all(isinstance(item, dict) and ("hosts" in item or "tasks" in item) for item in payload):
            return sum(_count_play_tasks(item, current_dir, stack) for item in payload if isinstance(item, dict))
        return _count_task_list(payload, current_dir, stack)

    if isinstance(payload, dict):
        if "hosts" in payload or "tasks" in payload:
            return _count_play_tasks(payload, current_dir, stack)
        return _count_task_list([payload], current_dir, stack)

    return 0


def count_playbook_tasks(playbook_path: Path) -> int:
    return _count_tasks_in_file(playbook_path, set())


def run_ansible_playbook(
    command: Sequence[str],
    *,
    playbook_path: Path,
    progress_header: Optional[str] = None,
    progress_handler: Optional[Callable[[int, int, str], None]] = None,
    progress_output: Optional[Callable[[str], None]] = None,
) -> AnsiblePlaybookResult:
    command_list = [str(part) for part in command]
    debug_log_command(command_list)

    if progress_handler and is_debug_enabled():
        progress_handler = None

    env = dict(os.environ)
    env["ANSIBLE_CONNECTION_PLUGINS"] = _merge_plugin_paths(
        env.get("ANSIBLE_CONNECTION_PLUGINS"),
        _ansible_plugins_dir("connection_plugins"),
    )

    if not is_debug_enabled():
        callback_dir = _ansible_plugins_dir("callback_plugins")
        if progress_handler:
            env["ANSIBLE_STDOUT_CALLBACK"] = "agsekit_rich"
        else:
            env["ANSIBLE_STDOUT_CALLBACK"] = _ANSIBLE_PROGRESS_CALLBACK
        env["ANSIBLE_LOAD_CALLBACK_PLUGINS"] = "1"
        env["ANSIBLE_CALLBACK_PLUGINS"] = _merge_plugin_paths(env.get("ANSIBLE_CALLBACK_PLUGINS"), callback_dir)
        env[_ANSIBLE_PROGRESS_TOTAL_ENV] = str(count_playbook_tasks(playbook_path))
        if progress_header:
            env[_ANSIBLE_PROGRESS_HEADER_ENV] = progress_header
        else:
            env.pop(_ANSIBLE_PROGRESS_HEADER_ENV, None)
    else:
        env.pop("ANSIBLE_STDOUT_CALLBACK", None)
        env.pop("ANSIBLE_LOAD_CALLBACK_PLUGINS", None)
        env.pop("ANSIBLE_CALLBACK_PLUGINS", None)
        env.pop(_ANSIBLE_PROGRESS_TOTAL_ENV, None)
        env.pop(_ANSIBLE_PROGRESS_HEADER_ENV, None)

    if progress_handler:
        process = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1,
        )
        output_lines: list[str] = []
        hidden_output_tail: Deque[str] = deque(maxlen=_ANSIBLE_HIDDEN_OUTPUT_TAIL_LINES)
        if process.stdout is not None:
            for line in process.stdout:
                stripped = line.strip()
                if stripped.startswith("AGSEKIT_PROGRESS "):
                    parts = stripped.split(" ", 3)
                    if len(parts) == 4:
                        try:
                            current = int(parts[1])
                            total = int(parts[2])
                        except ValueError:
                            continue
                        progress_handler(current, total, parts[3])
                    continue
                if stripped.startswith("AGSEKIT_FAILED "):
                    message = stripped.replace("AGSEKIT_FAILED ", "", 1)
                    _append_output_tail_line(hidden_output_tail, message)
                    continue
                if stripped.startswith("AGSEKIT_DETAIL "):
                    _append_output_tail_line(hidden_output_tail, stripped.replace("AGSEKIT_DETAIL ", "", 1))
                    continue
                output_lines.append(line)
                _append_output_tail_line(hidden_output_tail, line)
        return_code = process.wait()
        stdout_value = "".join(output_lines)
        result = AnsiblePlaybookResult(
            command_list,
            return_code,
            stdout=stdout_value,
            stderr=None,
            hidden_output_tail=tuple(hidden_output_tail),
        )
        debug_log_result(result)
        return result

    raw_result = subprocess.run(
        command_list,
        check=False,
        capture_output=False,
        text=True,
        env=env,
    )
    result = AnsiblePlaybookResult(
        command_list,
        raw_result.returncode,
        stdout=raw_result.stdout,
        stderr=raw_result.stderr,
    )
    debug_log_result(result)
    return result
