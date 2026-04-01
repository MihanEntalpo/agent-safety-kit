from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from agsekit_cli.ansible_utils import (
    AnsiblePlaybookResult,
    ansible_playbook_command,
    count_playbook_tasks,
    emit_hidden_output_tail,
    get_hidden_output_tail,
    run_ansible_playbook,
)


def _result(returncode: int = 0, stdout: str = "", stderr: str = ""):
    class Result:
        def __init__(self) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    return Result()


def test_ansible_playbook_command_uses_current_python():
    command = ansible_playbook_command()
    assert command == [sys.executable, "-m", "ansible.cli.playbook"]


def test_count_playbook_tasks_counts_blocks_and_includes():
    proxychains = Path("agsekit_cli/ansible/agents/proxychains.yml")
    opencode = Path("agsekit_cli/ansible/agents/opencode.yml")

    assert count_playbook_tasks(proxychains) == 7
    assert count_playbook_tasks(opencode) == 21


def test_run_ansible_playbook_uses_progress_callback_by_default(monkeypatch, tmp_path):
    playbook = tmp_path / "playbook.yml"
    playbook.write_text(
        """
- hosts: localhost
  gather_facts: false
  tasks:
    - name: demo
      ansible.builtin.command: true
""",
        encoding="utf-8",
    )
    calls = {}

    def fake_run(command, check=False, capture_output=False, text=False, env=None):
        del check, capture_output, text
        calls["command"] = command
        calls["env"] = env
        return _result(returncode=0)

    monkeypatch.delenv("AGSEKIT_DEBUG", raising=False)
    monkeypatch.setattr("agsekit_cli.ansible_utils.subprocess.run", fake_run)
    monkeypatch.setattr("agsekit_cli.ansible_utils.debug_log_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("agsekit_cli.ansible_utils.debug_log_result", lambda *_args, **_kwargs: None)

    run_ansible_playbook(
        ["ansible-playbook", "-i", "localhost,", str(playbook)],
        playbook_path=playbook,
        progress_header="Installing demo",
    )

    env = calls["env"]
    assert env is not None
    assert env["ANSIBLE_STDOUT_CALLBACK"] == "agsekit_progress"
    assert env["ANSIBLE_LOAD_CALLBACK_PLUGINS"] == "1"
    assert env["AGSEKIT_ANSIBLE_TOTAL_TASKS"] == "1"
    assert env["AGSEKIT_ANSIBLE_HEADER"] == "Installing demo"
    callback_path = env["ANSIBLE_CALLBACK_PLUGINS"].split(os.pathsep)[0]
    assert callback_path.endswith("agsekit_cli/ansible/callback_plugins")
    connection_path = env["ANSIBLE_CONNECTION_PLUGINS"].split(os.pathsep)[0]
    assert connection_path.endswith("agsekit_cli/ansible/connection_plugins")


def test_run_ansible_playbook_disables_progress_callback_in_debug(monkeypatch, tmp_path):
    playbook = tmp_path / "playbook.yml"
    playbook.write_text("[]\n", encoding="utf-8")
    calls = {}

    def fake_run(command, check=False, capture_output=False, text=False, env=None):
        del command, check, capture_output, text
        calls["env"] = env
        return _result(returncode=0)

    monkeypatch.setenv("AGSEKIT_DEBUG", "1")
    monkeypatch.setattr("agsekit_cli.ansible_utils.subprocess.run", fake_run)
    monkeypatch.setattr("agsekit_cli.ansible_utils.debug_log_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("agsekit_cli.ansible_utils.debug_log_result", lambda *_args, **_kwargs: None)

    run_ansible_playbook(["ansible-playbook", str(playbook)], playbook_path=playbook)

    env = calls["env"]
    assert env is not None
    assert "ANSIBLE_STDOUT_CALLBACK" not in env
    assert "ANSIBLE_CALLBACK_PLUGINS" not in env
    connection_path = env["ANSIBLE_CONNECTION_PLUGINS"].split(os.pathsep)[0]
    assert connection_path.endswith("agsekit_cli/ansible/connection_plugins")


def test_run_ansible_playbook_collects_hidden_output_tail(monkeypatch, tmp_path):
    playbook = tmp_path / "playbook.yml"
    playbook.write_text("[]\n", encoding="utf-8")
    progress_updates = []

    class DummyProcess:
        def __init__(self) -> None:
            self.stdout = iter(
                [
                    "AGSEKIT_PROGRESS 1 3 Install Node.js\n",
                    "hidden ordinary line\n",
                    "AGSEKIT_FAILED FAILED Install Node.js (agent-vm): boom\n",
                    "AGSEKIT_DETAIL cmd: /bin/false\n",
                    "AGSEKIT_DETAIL rc: 139\n",
                    "AGSEKIT_DETAIL stderr: Segmentation fault\n",
                ]
            )

        def wait(self) -> int:
            return 2

    monkeypatch.delenv("AGSEKIT_DEBUG", raising=False)
    monkeypatch.setattr("agsekit_cli.ansible_utils.subprocess.Popen", lambda *args, **kwargs: DummyProcess())
    monkeypatch.setattr("agsekit_cli.ansible_utils.debug_log_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("agsekit_cli.ansible_utils.debug_log_result", lambda *_args, **_kwargs: None)

    result = run_ansible_playbook(
        ["ansible-playbook", str(playbook)],
        playbook_path=playbook,
        progress_handler=lambda current, total, task_name: progress_updates.append((current, total, task_name)),
    )

    assert result.returncode == 2
    assert result.stdout == "hidden ordinary line\n"
    assert progress_updates == [(1, 3, "Install Node.js")]
    assert get_hidden_output_tail(result) == (
        "hidden ordinary line",
        "FAILED Install Node.js (agent-vm): boom",
        "cmd: /bin/false",
        "rc: 139",
        "stderr: Segmentation fault",
    )


def test_emit_hidden_output_tail_prints_last_lines(capsys):
    result = AnsiblePlaybookResult(
        ["ansible-playbook"],
        2,
        hidden_output_tail=["line 1", "line 2", "line 3"],
    )

    emit_hidden_output_tail(result, err=True, max_lines=2)

    captured = capsys.readouterr()
    assert "Last hidden Ansible lines:" in captured.err
    assert "line 2" in captured.err
    assert "line 3" in captured.err
    assert "line 1" not in captured.err


def _load_progress_callback_module():
    module_path = Path("agsekit_cli/ansible/callback_plugins/agsekit_progress.py")
    spec = importlib.util.spec_from_file_location("agsekit_progress_callback", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_rich_callback_module():
    module_path = Path("agsekit_cli/ansible/callback_plugins/agsekit_rich.py")
    spec = importlib.util.spec_from_file_location("agsekit_rich_callback", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_progress_callback_prints_header_step_and_bar(monkeypatch):
    module = _load_progress_callback_module()

    class DummyDisplay:
        def __init__(self):
            self.messages = []

        def display(self, message):
            self.messages.append(message)

    class DummyTask:
        def get_name(self):
            return "Check for node"

    dummy_display = DummyDisplay()
    monkeypatch.setattr(module, "display", dummy_display)
    monkeypatch.setenv("AGSEKIT_ANSIBLE_HEADER", "Installing agent in vm")
    monkeypatch.setenv("AGSEKIT_ANSIBLE_TOTAL_TASKS", "15")

    callback = module.CallbackModule()
    callback.v2_playbook_on_start(None)
    callback.v2_playbook_on_task_start(DummyTask(), False)

    assert dummy_display.messages[0] == "Installing agent in vm"
    assert dummy_display.messages[1].startswith("| 1/15 Check for node")
    assert dummy_display.messages[2].startswith("[")
    assert dummy_display.messages[2].endswith("]")


def test_progress_callback_prints_failure_details(monkeypatch):
    module = _load_progress_callback_module()

    class DummyDisplay:
        def __init__(self):
            self.messages = []

        def display(self, message):
            self.messages.append(message)

    class DummyTask:
        def get_name(self):
            return "Install Node.js"

    class DummyHost:
        def get_name(self):
            return "agent-vm"

    class DummyResult:
        _task = DummyTask()
        _host = DummyHost()
        _result = {"msg": "boom"}

    dummy_display = DummyDisplay()
    monkeypatch.setattr(module, "display", dummy_display)
    callback = module.CallbackModule()

    callback.v2_runner_on_failed(DummyResult(), ignore_errors=False)

    assert dummy_display.messages[-1] == "FAILED Install Node.js (agent-vm): boom"


def test_rich_callback_emits_failure_detail_control_lines(monkeypatch):
    module = _load_rich_callback_module()
    emitted = []

    class DummyTask:
        def get_name(self):
            return "Install Node.js"

    class DummyHost:
        def get_name(self):
            return "agent-vm"

    class DummyResult:
        _task = DummyTask()
        _host = DummyHost()
        _result = {
            "msg": "boom",
            "cmd": "/bin/false",
            "rc": 139,
            "delta": "0:00:00.01",
            "stderr": "Segmentation fault",
            "stdout_lines": ["line one", "line two"],
        }

    callback = module.CallbackModule()
    monkeypatch.setattr(callback, "_emit", emitted.append)

    callback.v2_runner_on_failed(DummyResult(), ignore_errors=False)

    assert emitted[0] == "AGSEKIT_FAILED FAILED Install Node.js (agent-vm): boom"
    assert "AGSEKIT_DETAIL cmd: /bin/false" in emitted
    assert "AGSEKIT_DETAIL rc: 139" in emitted
    assert "AGSEKIT_DETAIL delta: 0:00:00.01" in emitted
    assert "AGSEKIT_DETAIL stderr: Segmentation fault" in emitted
    assert "AGSEKIT_DETAIL stdout_lines: line one" in emitted
    assert "AGSEKIT_DETAIL stdout_lines: line two" in emitted


def test_progress_callback_overwrites_previous_lines_in_tty(monkeypatch):
    module = _load_progress_callback_module()

    class DummyStdout:
        def __init__(self):
            self.chunks: list[str] = []

        def isatty(self) -> bool:
            return True

        def write(self, chunk: str) -> int:
            self.chunks.append(chunk)
            return len(chunk)

        def flush(self) -> None:
            return None

    stdout = DummyStdout()
    monkeypatch.setattr(module.sys, "stdout", stdout)
    callback = module.CallbackModule()

    callback._active_task = "Task A"
    callback._current = 1
    callback._total = 2
    callback._render_progress("|")

    callback._active_task = "Task B"
    callback._current = 2
    callback._render_progress("/")

    output = "".join(stdout.chunks)
    assert "\x1b[2F" in output


def test_progress_callback_expands_total_when_tasks_exceed_estimate(monkeypatch):
    module = _load_progress_callback_module()

    class DummyDisplay:
        def __init__(self):
            self.messages = []

        def display(self, message):
            self.messages.append(message)

    class DummyTask:
        def __init__(self, name: str):
            self._name = name

        def get_name(self):
            return self._name

    dummy_display = DummyDisplay()
    monkeypatch.setattr(module, "display", dummy_display)
    monkeypatch.setenv("AGSEKIT_ANSIBLE_TOTAL_TASKS", "1")

    callback = module.CallbackModule()
    callback.v2_playbook_on_task_start(DummyTask("First"), False)
    callback.v2_playbook_on_task_start(DummyTask("Second"), False)

    assert dummy_display.messages[2].startswith("| 2/2 Second")


def test_progress_callback_clears_lines_after_success_stats(monkeypatch):
    module = _load_progress_callback_module()

    class DummyStdout:
        def __init__(self):
            self.chunks: list[str] = []

        def isatty(self) -> bool:
            return True

        def write(self, chunk: str) -> int:
            self.chunks.append(chunk)
            return len(chunk)

        def flush(self) -> None:
            return None

    class DummyStats:
        processed = {"agent-vm": True}

        @staticmethod
        def summarize(_host):
            return {"failures": 0, "unreachable": 0}

    stdout = DummyStdout()
    monkeypatch.setattr(module.sys, "stdout", stdout)
    callback = module.CallbackModule()
    callback._active_task = "Task"
    callback._current = 1
    callback._total = 1
    callback._render_progress("o")

    callback.v2_playbook_on_stats(DummyStats())

    output = "".join(stdout.chunks)
    assert "\x1b[2F" in output
    assert "\x1b[2K" in output
