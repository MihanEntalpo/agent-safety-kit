import agsekit_cli.commands.portforward as portforward_module
from agsekit_cli import cli_entry


def test_resolve_agsekit_command_prefers_current_cli_path(monkeypatch, tmp_path):
    current_cli = tmp_path / "current" / "agsekit"
    current_cli.parent.mkdir(parents=True)
    current_cli.write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(cli_entry.sys, "argv", [str(current_cli)])
    monkeypatch.setattr(cli_entry.shutil, "which", lambda _name: None)

    assert portforward_module._resolve_agsekit_command() == [str(current_cli.resolve())]


def test_resolve_agsekit_command_falls_back_to_current_python(monkeypatch):
    monkeypatch.setattr(portforward_module.cli_entry, "resolve_agsekit_script_path", lambda: None)

    assert portforward_module._resolve_agsekit_command() == [cli_entry.sys.executable, "-m", "agsekit_cli.cli"]
