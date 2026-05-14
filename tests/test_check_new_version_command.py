from __future__ import annotations

from types import SimpleNamespace

from click.testing import CliRunner

from agsekit_cli import state as state_module
from agsekit_cli.commands.check_new_version import check_new_version_command


def test_check_new_version_reports_newer_version_and_updates_state(monkeypatch, tmp_path):
    state_path = tmp_path / "state.yaml"
    monkeypatch.setattr(
        state_module,
        "load_global_config_from_path",
        lambda *_args, **_kwargs: SimpleNamespace(state_file=state_path),
    )
    monkeypatch.setattr(state_module, "runtime_version", lambda: "1.6.9")
    monkeypatch.setattr(state_module, "latest_version_via_pip", lambda *_args, **_kwargs: "1.7.0")
    monkeypatch.setattr(state_module, "_STATE_MANAGER", None)

    runner = CliRunner()
    result = runner.invoke(check_new_version_command, [])

    assert result.exit_code == 0
    assert "A newer agsekit version is available: 1.7.0 (current: 1.6.9)." in result.output
    assert "last_Version: 1.7.0" in state_path.read_text(encoding="utf-8")


def test_check_new_version_reports_already_latest(monkeypatch, tmp_path):
    state_path = tmp_path / "state.yaml"
    monkeypatch.setattr(
        state_module,
        "load_global_config_from_path",
        lambda *_args, **_kwargs: SimpleNamespace(state_file=state_path),
    )
    monkeypatch.setattr(state_module, "runtime_version", lambda: "1.6.9")
    monkeypatch.setattr(state_module, "latest_version_via_pip", lambda *_args, **_kwargs: "1.6.9")
    monkeypatch.setattr(state_module, "_STATE_MANAGER", None)

    runner = CliRunner()
    result = runner.invoke(check_new_version_command, [])

    assert result.exit_code == 0
    assert "already at the latest known version: 1.6.9" in result.output
