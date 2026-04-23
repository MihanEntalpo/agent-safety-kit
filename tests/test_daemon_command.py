from pathlib import Path

from click.testing import CliRunner

import agsekit_cli.commands.daemon as daemon_module


class DummyBackend:
    def __init__(self, *, supported=True, status_lines=None):
        self.supported = supported
        self._status_lines = status_lines or ["status line"]
        self.calls = []

    def install(self, config_path, *, project_dir=None, announce=True):
        self.calls.append(("install", config_path, project_dir, announce))

    def uninstall(self, *, project_dir=None, announce=True):
        self.calls.append(("uninstall", project_dir, announce))

    def start(self, *, announce=True):
        self.calls.append(("start", announce))

    def stop(self, *, announce=True):
        self.calls.append(("stop", announce))

    def restart(self, *, announce=True):
        self.calls.append(("restart", announce))

    def stop_if_installed(self, *, announce=True):
        self.calls.append(("stop_if_installed", announce))
        return True

    def status_lines(self):
        return list(self._status_lines)


def test_daemon_install_command_is_quiet_without_debug(monkeypatch, tmp_path):
    backend = DummyBackend()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("vms: {}\n", encoding="utf-8")

    monkeypatch.setattr(daemon_module, "get_daemon_backend", lambda: backend)

    runner = CliRunner()
    result = runner.invoke(daemon_module.daemon_group, ["install", "--config", str(config_path)])

    assert result.exit_code == 0
    assert backend.calls == [("install", config_path, Path.cwd(), False)]
    assert result.output.splitlines() == [
        "Installing/updating portforward daemon...",
        "Portforward daemon installed successfully.",
    ]


def test_daemon_status_prints_backend_specific_lines(monkeypatch):
    backend = DummyBackend(status_lines=["line 1", "line 2"])
    monkeypatch.setattr(daemon_module, "get_daemon_backend", lambda: backend)

    runner = CliRunner()
    result = runner.invoke(daemon_module.daemon_group, ["status"])

    assert result.exit_code == 0
    assert result.output.splitlines() == ["line 1", "line 2"]


def test_daemon_warns_on_unsupported_platform(monkeypatch):
    backend = DummyBackend(supported=False)
    monkeypatch.setattr(daemon_module, "get_daemon_backend", lambda: backend)
    monkeypatch.setattr(daemon_module, "platform_label", lambda: "Windows")

    runner = CliRunner()
    result = runner.invoke(daemon_module.daemon_group, ["install"])

    assert result.exit_code == 0
    assert backend.calls == []
    assert "Windows" in result.output
    assert "not implemented yet" in result.output
