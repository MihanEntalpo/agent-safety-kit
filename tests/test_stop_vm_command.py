import sys
import json
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.stop as stop_module
from agsekit_cli.commands.stop import stop_vm_command


def _write_config(config_path: Path, vm_names: list[str]) -> None:
    entries = "\n".join(f"  {name}:\n    cpu: 1\n    ram: 1G\n    disk: 5G" for name in vm_names)
    config_path.write_text(f"vms:\n{entries}\n", encoding="utf-8")


def _result(*, returncode: int = 0, stdout: str = "", stderr: str = ""):
    class Result:
        pass

    result = Result()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def test_stop_single_vm(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    calls: list[list[str]] = []
    sleep_calls: list[int] = []

    def fake_run(command, check=False, capture_output=False, text=False):
        calls.append(command)
        if command == ["multipass", "list", "--format", "json"]:
            return _result(stdout=json.dumps({"list": [{"name": "agent", "state": "Stopped"}]}))
        return _result()

    monkeypatch.setattr(stop_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(stop_module.subprocess, "run", fake_run)
    monkeypatch.setattr(stop_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    runner = CliRunner()
    result = runner.invoke(stop_vm_command, ["agent", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [
        ["multipass", "exec", "agent", "--", "sudo", "poweroff"],
        ["multipass", "list", "--format", "json"],
    ]
    assert sleep_calls == [30]


def test_stop_defaults_to_single_vm(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    calls: list[list[str]] = []
    sleep_calls: list[int] = []

    def fake_run(command, check=False, capture_output=False, text=False):
        calls.append(command)
        if command == ["multipass", "list", "--format", "json"]:
            return _result(stdout=json.dumps({"list": [{"name": "agent", "state": "Stopped"}]}))
        return _result()

    monkeypatch.setattr(stop_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(stop_module.subprocess, "run", fake_run)
    monkeypatch.setattr(stop_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    runner = CliRunner()
    result = runner.invoke(stop_vm_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [
        ["multipass", "exec", "agent", "--", "sudo", "poweroff"],
        ["multipass", "list", "--format", "json"],
    ]
    assert sleep_calls == [30]


def test_stop_all_vms(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["vm1", "vm2"])

    calls: list[list[str]] = []
    sleep_calls: list[int] = []

    def fake_run(command, check=False, capture_output=False, text=False):
        calls.append(command)
        if command == ["multipass", "list", "--format", "json"]:
            return _result(
                stdout=json.dumps(
                    {
                        "list": [
                            {"name": "vm1", "state": "Stopped"},
                            {"name": "vm2", "state": "Stopped"},
                        ]
                    }
                )
            )
        return _result()

    monkeypatch.setattr(stop_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(stop_module.subprocess, "run", fake_run)
    monkeypatch.setattr(stop_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    runner = CliRunner()
    result = runner.invoke(stop_vm_command, ["--all-vms", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [
        ["multipass", "exec", "vm1", "--", "sudo", "poweroff"],
        ["multipass", "list", "--format", "json"],
        ["multipass", "exec", "vm2", "--", "sudo", "poweroff"],
        ["multipass", "list", "--format", "json"],
    ]
    assert sleep_calls == [30, 30]


def test_stop_requires_vm_name_when_multiple(monkeypatch, tmp_path):
    monkeypatch.setenv("AGSEKIT_LANG", "ru")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["first", "second"])

    monkeypatch.setattr(stop_module, "ensure_multipass_available", lambda: None)

    runner = CliRunner()
    result = runner.invoke(stop_vm_command, ["--config", str(config_path)])

    assert result.exit_code != 0
    assert "Укажите имя ВМ" in result.output


def test_stop_vm_debug_output(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    def fake_run(command, check=False, capture_output=False, text=False):
        if command == ["multipass", "list", "--format", "json"]:
            return _result(stdout=json.dumps({"list": [{"name": "agent", "state": "Stopped"}]}))
        return _result(stdout="stopped")

    monkeypatch.setattr(stop_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(stop_module.subprocess, "run", fake_run)
    monkeypatch.setattr(stop_module.time, "sleep", lambda *_: None)

    runner = CliRunner()
    result = runner.invoke(
        stop_vm_command,
        ["agent", "--config", str(config_path), "--debug"],
        env={"AGSEKIT_LANG": "en"},
    )

    assert result.exit_code == 0
    assert "[DEBUG] command: multipass exec agent -- sudo poweroff" in result.output
    assert "[DEBUG] command: multipass list --format json" in result.output
    assert "[DEBUG] exit code: 0" in result.output


def test_stop_uses_force_if_vm_stays_running(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    calls: list[list[str]] = []
    sleep_calls: list[int] = []

    def fake_run(command, check=False, capture_output=False, text=False):
        calls.append(command)
        if command == ["multipass", "list", "--format", "json"]:
            return _result(stdout=json.dumps({"list": [{"name": "agent", "state": "Running"}]}))
        return _result()

    monkeypatch.setattr(stop_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(stop_module.subprocess, "run", fake_run)
    monkeypatch.setattr(stop_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    runner = CliRunner()
    result = runner.invoke(stop_vm_command, ["agent", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [
        ["multipass", "exec", "agent", "--", "sudo", "poweroff"],
        ["multipass", "list", "--format", "json"],
        ["multipass", "stop", "--force", "agent"],
    ]
    assert sleep_calls == [30]
