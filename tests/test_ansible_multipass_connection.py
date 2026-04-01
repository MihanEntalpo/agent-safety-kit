from __future__ import annotations

import importlib.util
from pathlib import Path

from ansible.playbook.play_context import PlayContext


def _load_connection_module():
    module_path = Path("agsekit_cli/ansible/connection_plugins/agsekit_multipass.py")
    spec = importlib.util.spec_from_file_location("agsekit_multipass_connection", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _connection():
    module = _load_connection_module()
    play_context = PlayContext()
    play_context.remote_addr = "agent-ubuntu"
    return module.Connection(play_context)


def test_exec_command_uses_multipass_exec(monkeypatch):
    connection = _connection()
    captured = {}

    class DummyProcess:
        def __init__(self, command, stdin=None, stdout=None, stderr=None):
            del stdin, stdout, stderr
            captured["command"] = command

        def communicate(self, in_data=None):
            captured["in_data"] = in_data
            return b"ok\n", b""

        @property
        def returncode(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProcess)

    returncode, stdout, stderr = connection.exec_command("echo ok", in_data=b"payload")

    assert returncode == 0
    assert stdout == b"ok\n"
    assert stderr == b""
    assert captured["command"] == ["multipass", "exec", "agent-ubuntu", "--", "/bin/sh", "-c", "echo ok"]
    assert captured["in_data"] == b"payload"


def test_put_file_stages_hidden_local_source_before_transfer(monkeypatch, tmp_path):
    connection = _connection()
    source = tmp_path / ".ansible" / "tmp" / "source.txt"
    source.parent.mkdir(parents=True)
    source.write_text("data", encoding="utf-8")
    captured = {}

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, check=False, capture_output=False, text=False):
        del check, capture_output, text
        captured["command"] = command
        captured["staged_path"] = command[2]
        captured["staged_content"] = Path(command[2]).read_text(encoding="utf-8")
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)

    connection.put_file(str(source), "/tmp/remote.txt")

    assert captured["command"][0:2] == ["multipass", "transfer"]
    assert captured["command"][3] == "agent-ubuntu:/tmp/remote.txt"
    assert captured["command"][2] != str(source)
    assert captured["staged_content"] == "data"
    assert not Path(captured["staged_path"]).exists()


def test_fetch_file_stages_hidden_local_destination_before_finalize(monkeypatch, tmp_path):
    connection = _connection()
    destination = tmp_path / ".ansible" / "tmp" / "remote.txt"
    captured = {}

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, check=False, capture_output=False, text=False):
        del check, capture_output, text
        captured["command"] = command
        captured["staged_path"] = command[3]
        Path(command[3]).write_text("downloaded", encoding="utf-8")
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)

    connection.fetch_file("/tmp/remote.txt", str(destination))

    assert destination.parent.exists()
    assert destination.read_text(encoding="utf-8") == "downloaded"
    assert captured["command"] == ["multipass", "transfer", "agent-ubuntu:/tmp/remote.txt", captured["staged_path"]]
    assert "agsekit-multipass-fetch-" in Path(captured["staged_path"]).name
    assert not Path(captured["staged_path"]).exists()
