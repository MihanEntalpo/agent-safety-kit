from pathlib import Path

from click.testing import CliRunner

import agsekit_cli.commands.config_edit as config_edit_module
from agsekit_cli.commands.config_edit import config_edit_command


def test_config_edit_uses_editor_and_explicit_config_path(monkeypatch, tmp_path):
    config_path = tmp_path / "nested" / "config.yaml"
    calls = {}

    class Result:
        returncode = 0

    monkeypatch.setenv("EDITOR", "fake-editor --wait")
    monkeypatch.setattr(config_edit_module.shutil, "which", lambda name: "/bin/fake-editor" if name == "fake-editor" else None)
    monkeypatch.setattr(
        config_edit_module.subprocess,
        "run",
        lambda command, check=False: calls.setdefault("command", command) and Result(),
    )

    result = CliRunner().invoke(config_edit_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls["command"] == ["fake-editor", "--wait", str(config_path.resolve())]
    assert config_path.parent.is_dir()


def test_config_edit_uses_config_path_environment_variable(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    calls = {}

    class Result:
        returncode = 0

    monkeypatch.setenv("EDITOR", "editor")
    monkeypatch.setenv("CONFIG_PATH", str(config_path))
    monkeypatch.setattr(config_edit_module.shutil, "which", lambda _name: "/bin/editor")
    monkeypatch.setattr(
        config_edit_module.subprocess,
        "run",
        lambda command, check=False: calls.setdefault("command", command) and Result(),
    )

    result = CliRunner().invoke(config_edit_command, [])

    assert result.exit_code == 0
    assert calls["command"] == ["editor", str(config_path.resolve())]


def test_config_edit_offers_only_installed_fallback_editors(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    calls = {}

    class Result:
        returncode = 0

    class Question:
        def ask(self):
            return "nano"

    def fake_select(_message, *, choices, **_kwargs):
        calls["choices"] = [choice.value for choice in choices]
        return Question()

    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr(config_edit_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(config_edit_module.shutil, "which", lambda name: "/bin/nano" if name == "nano" else None)
    monkeypatch.setattr(config_edit_module.questionary, "select", fake_select)
    monkeypatch.setattr(
        config_edit_module.subprocess,
        "run",
        lambda command, check=False: calls.setdefault("command", command) and Result(),
    )

    result = CliRunner().invoke(config_edit_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls["choices"] == ["nano"]
    assert calls["command"] == ["nano", str(config_path.resolve())]


def test_config_edit_requires_editor_without_prompt(monkeypatch, tmp_path):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr(config_edit_module.shutil, "which", lambda _name: None)

    result = CliRunner().invoke(
        config_edit_command,
        ["--config", str(tmp_path / "config.yaml"), "--non-interactive"],
    )

    assert result.exit_code != 0
    assert "set EDITOR" in result.output


def test_config_edit_reports_unavailable_editor_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("EDITOR", "missing-editor")
    monkeypatch.setattr(config_edit_module.shutil, "which", lambda _name: None)

    result = CliRunner().invoke(config_edit_command, ["--config", str(tmp_path / "config.yaml")])

    assert result.exit_code != 0
    assert "missing-editor" in result.output
