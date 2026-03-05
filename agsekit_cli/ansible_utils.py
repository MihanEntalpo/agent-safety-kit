from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import click
import yaml

from .debug import debug_log_command, debug_log_result, is_debug_enabled
from .i18n import tr


class AnsibleCollectionError(RuntimeError):
    """Raised when required ansible collection cannot be installed."""


_ANSIBLE_PROGRESS_CALLBACK = "agsekit_progress"
_ANSIBLE_PROGRESS_TOTAL_ENV = "AGSEKIT_ANSIBLE_TOTAL_TASKS"
_ANSIBLE_PROGRESS_HEADER_ENV = "AGSEKIT_ANSIBLE_HEADER"


def _ansible_galaxy_command() -> list[str]:
    return [sys.executable, "-m", "ansible.cli.galaxy"]


def ansible_playbook_command() -> list[str]:
    return [sys.executable, "-m", "ansible.cli.playbook"]


def _callback_plugins_dir() -> Path:
    return Path(__file__).resolve().parent / "ansible" / "callback_plugins"


def _merge_callback_plugin_paths(existing: Optional[str], custom: Path) -> str:
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
) -> subprocess.CompletedProcess[str]:
    command_list = [str(part) for part in command]
    debug_log_command(command_list)

    env = None
    if not is_debug_enabled():
        callback_dir = _callback_plugins_dir()
        env = dict(os.environ)
        env["ANSIBLE_STDOUT_CALLBACK"] = _ANSIBLE_PROGRESS_CALLBACK
        env["ANSIBLE_LOAD_CALLBACK_PLUGINS"] = "1"
        env["ANSIBLE_CALLBACK_PLUGINS"] = _merge_callback_plugin_paths(env.get("ANSIBLE_CALLBACK_PLUGINS"), callback_dir)
        env[_ANSIBLE_PROGRESS_TOTAL_ENV] = str(count_playbook_tasks(playbook_path))
        if progress_header:
            env[_ANSIBLE_PROGRESS_HEADER_ENV] = progress_header
        else:
            env.pop(_ANSIBLE_PROGRESS_HEADER_ENV, None)

    result = subprocess.run(
        command_list,
        check=False,
        capture_output=False,
        text=True,
        env=env,
    )
    debug_log_result(result)
    return result


def ensure_multipass_collection() -> None:
    galaxy_command = _ansible_galaxy_command()
    list_command = [*galaxy_command, "collection", "list", "theko2fi.multipass"]
    debug_log_command(list_command)
    try:
        list_result = subprocess.run(
            list_command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise AnsibleCollectionError(
            tr("prepare.ansible_galaxy_missing", python=sys.executable)
        ) from exc
    debug_log_result(list_result)

    if list_result.returncode == 0 and "theko2fi.multipass" in (list_result.stdout or ""):
        return

    click.echo(tr("prepare.installing_ansible_collection"))
    install_command = [*galaxy_command, "collection", "install", "theko2fi.multipass"]
    debug_log_command(install_command)
    try:
        install_result = subprocess.run(
            install_command,
            check=False,
            capture_output=False,
            text=True,
        )
    except FileNotFoundError as exc:
        raise AnsibleCollectionError(
            tr("prepare.ansible_galaxy_missing", python=sys.executable)
        ) from exc
    debug_log_result(install_result)

    if install_result.returncode != 0:
        raise AnsibleCollectionError(tr("prepare.installing_ansible_collection_failed"))
