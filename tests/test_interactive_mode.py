from __future__ import annotations

import sys
from typing import Any, Dict

from pathlib import Path

import click
import pytest

import agsekit_cli.cli as cli_module
import agsekit_cli.interactive as interactive
import agsekit_cli.config as config_module
from agsekit_cli.config import AgentConfig, MountConfig


class DummyPrompt:
    def __init__(self, value: Any):
        self._value = value

    def ask(self) -> Any:
        return self._value


class DummyQuestionary:
    class Choice:
        def __init__(self, title: str, value: Any = None):
            self.title = title
            self.value = value

    @staticmethod
    def confirm(*_args: Any, **_kwargs: Any) -> DummyPrompt:
        return DummyPrompt(True)


@pytest.fixture(autouse=True)
def restore_sys_argv(monkeypatch):
    original = sys.argv[:]
    yield
    monkeypatch.setattr(sys, "argv", original)


def test_main_triggers_interactive_without_args(monkeypatch):
    called: Dict[str, Any] = {}

    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit"])

    def fake_run(cli, preselected_command=None, default_config_path=None):
        called["cli"] = cli
        called["preselected"] = preselected_command
        called["default_config_path"] = default_config_path

    monkeypatch.setattr(cli_module, "run_interactive", fake_run)

    cli_module.main()

    assert called["cli"] is cli_module.cli
    assert called["preselected"] is None


def test_main_falls_back_to_interactive_on_missing_params(monkeypatch):
    called: Dict[str, Any] = {}

    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit", "create-vm"])

    def fake_run(cli, preselected_command=None, default_config_path=None):
        called["cli"] = cli
        called["preselected"] = preselected_command
        called["default_config_path"] = default_config_path

    monkeypatch.setattr(cli_module, "run_interactive", fake_run)

    cli_module.main()

    assert called["cli"] is cli_module.cli
    assert called["preselected"] == "create-vm"
    assert called["default_config_path"] == config_module.DEFAULT_CONFIG_PATH


def test_main_prompts_for_config_when_missing(monkeypatch, tmp_path):
    called: Dict[str, Any] = {}
    missing_config = tmp_path / "absent.yaml"

    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit", "run", "qwen", str(tmp_path)])
    monkeypatch.setattr(cli_module, "resolve_config_path", lambda _path=None: missing_config)

    def fake_run(cli, preselected_command=None, default_config_path=None):
        called["cli"] = cli
        called["preselected"] = preselected_command
        called["default_config_path"] = default_config_path

    monkeypatch.setattr(cli_module, "run_interactive", fake_run)

    cli_module.main()

    assert called["cli"] is cli_module.cli
    assert called["preselected"] == "run"
    assert called["default_config_path"] == missing_config


def test_run_interactive_executes_selected_command(monkeypatch):
    dummy_cli = click.Group()

    @dummy_cli.command(name="prepare")
    def prepare_command():
        pass

    monkeypatch.setattr(interactive, "_command_builders", lambda: {"prepare": lambda session: ["prepare"]})

    executed: Dict[str, Any] = {}

    def fake_main(*, args, prog_name):
        executed["args"] = args
        executed["prog_name"] = prog_name

    monkeypatch.setattr(dummy_cli, "main", fake_main)
    monkeypatch.setattr(interactive, "questionary", DummyQuestionary)

    interactive.run_interactive(dummy_cli, preselected_command="prepare")

    assert executed["args"] == ["prepare"]
    assert executed["prog_name"] == "agsekit"


def test_main_keeps_standard_help_when_not_interactive(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: False)
    monkeypatch.setattr(sys, "argv", ["agsekit", "--help"])

    cli_module.main()

    captured = capsys.readouterr()
    assert "Agent Safety Kit CLI" in captured.out


def test_main_skips_interactive_when_flag_is_set(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit", "--non-interactive"])

    def fail_if_called(*_args: Any, **_kwargs: Any) -> None:  # pragma: no cover - defensive
        raise AssertionError("interactive mode should not be invoked when --non-interactive is provided")

    monkeypatch.setattr(cli_module, "run_interactive", fail_if_called)

    cli_module.main()

    captured = capsys.readouterr()
    assert "Agent Safety Kit CLI" in captured.out


def test_main_reports_missing_params_without_interactive_when_flag_is_set(monkeypatch):
    called: Dict[str, Any] = {"interactive": False}

    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit", "create-vm", "--non-interactive"])

    def mark_called(*_args: Any, **_kwargs: Any) -> None:  # pragma: no cover - defensive
        called["interactive"] = True

    monkeypatch.setattr(cli_module, "run_interactive", mark_called)

    with pytest.raises(SystemExit) as excinfo:
        cli_module.main()

    assert excinfo.value.code == 1
    assert called["interactive"] is False


def test_main_reports_missing_config_without_interactive(monkeypatch, tmp_path):
    missing_config = tmp_path / "absent.yaml"
    called: Dict[str, Any] = {"interactive": False}

    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit", "run", "qwen", str(tmp_path), "--non-interactive"])
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", missing_config)

    def mark_called(*_args: Any, **_kwargs: Any) -> None:  # pragma: no cover - defensive
        called["interactive"] = True

    monkeypatch.setattr(cli_module, "run_interactive", mark_called)

    with pytest.raises(SystemExit) as excinfo:
        cli_module.main()

    assert excinfo.value.code == 1
    assert called["interactive"] is False


def test_build_run_skips_vm_argument_when_auto_selected(monkeypatch, tmp_path):
    agent = AgentConfig(name="qwen", type="qwen", env={}, vm_name=None)
    mount = MountConfig(
        source=tmp_path,
        target=Path("/home/ubuntu/project"),
        backup=tmp_path / "backups",
        interval_minutes=5,
        vm_name="agents-ubuntu",
    )

    class DummySession:
        def load_agents(self):
            return {"qwen": agent}

        def load_mounts(self):
            return [mount]

        def load_vms(self):
            return {"agents-ubuntu": object()}

        def config_option(self):
            return ["--config", "config.yaml"]

    selections = [agent, mount, "__auto_vm__"]
    confirms = [False]
    texts = [""]

    class Prompt:
        def __init__(self, value):
            self.value = value

        def ask(self):
            return self.value

    class FakeQuestionary:
        @staticmethod
        def select(*_args, **_kwargs):
            return Prompt(selections.pop(0))

        @staticmethod
        def confirm(*_args, **_kwargs):
            return Prompt(confirms.pop(0))

        @staticmethod
        def text(*_args, **_kwargs):
            return Prompt(texts.pop(0))

    FakeQuestionary.Choice = interactive.questionary.Choice

    monkeypatch.setattr(interactive, "questionary", FakeQuestionary)

    args = interactive.build_run(DummySession())

    assert args == ["run", "qwen", str(tmp_path), "--config", "config.yaml"]
