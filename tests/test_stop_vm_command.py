import sys
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


def test_stop_single_vm(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    calls: list[list[str]] = []

    def fake_run(command, check=False, capture_output=False, text=False):
        calls.append(command)

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        return Result()

    monkeypatch.setattr(stop_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(stop_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(stop_vm_command, ["agent", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [["multipass", "stop", "agent"]]


def test_stop_defaults_to_single_vm(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    calls: list[list[str]] = []

    def fake_run(command, check=False, capture_output=False, text=False):
        calls.append(command)

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        return Result()

    monkeypatch.setattr(stop_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(stop_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(stop_vm_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [["multipass", "stop", "agent"]]


def test_stop_all_vms(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["vm1", "vm2"])

    calls: list[list[str]] = []

    def fake_run(command, check=False, capture_output=False, text=False):
        calls.append(command)

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        return Result()

    monkeypatch.setattr(stop_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(stop_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(stop_vm_command, ["--all-vms", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [["multipass", "stop", "vm1"], ["multipass", "stop", "vm2"]]


def test_stop_requires_vm_name_when_multiple(monkeypatch, tmp_path):
    monkeypatch.setenv("AGSEKIT_LANG", "ru")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["first", "second"])

    monkeypatch.setattr(stop_module, "ensure_multipass_available", lambda: None)

    runner = CliRunner()
    result = runner.invoke(stop_vm_command, ["--config", str(config_path)])

    assert result.exit_code != 0
    assert "Укажите имя ВМ" in result.output
