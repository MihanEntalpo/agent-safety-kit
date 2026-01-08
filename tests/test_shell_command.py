import sys
from pathlib import Path
from typing import Optional

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.shell as shell_module
from agsekit_cli.commands.shell import shell_command


def _write_config(config_path: Path, vm_names: list[str], proxychains: Optional[str] = None) -> None:
    entries = "\n".join(
        f"  {name}:\n    cpu: 1\n    ram: 1G\n    disk: 5G{f'\n    proxychains: \"{proxychains}\"' if proxychains is not None else ''}"
        for name in vm_names
    )
    config_path.write_text(f"vms:\n{entries}\n", encoding="utf-8")


def test_shell_command_uses_explicit_vm(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    calls: dict[str, object] = {}

    def fake_run(command, check=False):
        calls["command"] = command

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(shell_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(shell_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(shell_command, ["agent", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls["command"] == ["multipass", "shell", "agent"]


def test_shell_command_uses_single_vm_when_missing_arg(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["default"])

    captured: dict[str, object] = {}

    def fake_run(command, check=False):
        captured["command"] = command

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(shell_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(shell_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(shell_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert captured["command"] == ["multipass", "shell", "default"]


def test_shell_command_prompts_for_vm_when_several(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["vm1", "vm2"])

    def fake_run(command, check=False):

        class Result:
            returncode = 0

        return Result()

    class DummyQuestion:
        def ask(self):
            return "vm2"

    monkeypatch.setattr(shell_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(shell_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(shell_module.questionary, "select", lambda *_, **__: DummyQuestion())
    monkeypatch.setattr(shell_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(shell_command, ["--config", str(config_path)])

    assert result.exit_code == 0


def test_shell_command_requires_vm_name_in_non_interactive(monkeypatch, tmp_path):
    monkeypatch.setenv("AGSEKIT_LANG", "ru")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["vm1", "vm2"])

    monkeypatch.setattr(shell_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(shell_module, "is_interactive_terminal", lambda: False)

    runner = CliRunner()
    result = runner.invoke(shell_command, ["--config", str(config_path), "--non-interactive"])

    assert result.exit_code != 0
    assert "Укажите имя ВМ" in result.output


def test_shell_command_ignores_proxychains_from_config(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"], proxychains="socks5://127.0.0.1:8080")

    calls: dict[str, object] = {}

    def fake_run(command, check=False):
        calls["command"] = command

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(shell_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(shell_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(shell_command, ["agent", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls["command"] == ["multipass", "shell", "agent"]
