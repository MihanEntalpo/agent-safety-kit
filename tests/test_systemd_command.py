import subprocess
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from agsekit_cli import cli_entry, systemd_backend
import agsekit_cli.commands.daemon as daemon_module
import agsekit_cli.commands.systemd as systemd_alias_module


def test_packaged_systemd_unit_uses_shell_wrapper_for_env_expansion():
    unit_path = Path("agsekit_cli/systemd/agsekit-portforward.service")
    contents = unit_path.read_text(encoding="utf-8")

    assert 'ExecStart=/bin/bash -lc \'exec "$AGSEKIT_BIN" portforward --config "$AGSEKIT_CONFIG"\'' in contents


def test_resolve_agsekit_bin_prefers_current_cli_path(monkeypatch, tmp_path):
    current_cli = tmp_path / "current" / "agsekit"
    current_cli.parent.mkdir(parents=True)
    current_cli.write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(cli_entry.sys, "argv", [str(current_cli)])
    monkeypatch.setattr(cli_entry.shutil, "which", lambda _name: "/tmp/stale/agsekit")

    assert systemd_backend.resolve_agsekit_bin() == current_cli.resolve()


def test_install_portforward_service_relinks_existing_unit_to_current_installation(monkeypatch, tmp_path):
    current_project = tmp_path / "current"
    current_unit = current_project / "agsekit_cli" / "systemd" / "agsekit-portforward.service"
    current_unit.parent.mkdir(parents=True)
    current_unit.write_text("[Unit]\nDescription=current\n", encoding="utf-8")

    old_project = tmp_path / "old"
    old_unit = old_project / "agsekit_cli" / "systemd" / "agsekit-portforward.service"
    old_unit.parent.mkdir(parents=True)
    old_unit.write_text("[Unit]\nDescription=old\n", encoding="utf-8")

    linked_unit = tmp_path / "user-systemd" / "agsekit-portforward.service"
    linked_unit.parent.mkdir(parents=True)
    linked_unit.symlink_to(old_unit)

    config_path = tmp_path / "config.yaml"
    env_dir = tmp_path / "agsekit-config"
    compatibility_env_dir = tmp_path / "compatibility-env"
    config_path.write_text(
        f"global:\n  systemd_env_folder: {env_dir}\nvms: {{}}\n",
        encoding="utf-8",
    )
    commands = []

    monkeypatch.setattr(systemd_backend, "LINKED_UNIT_PATH", linked_unit)
    monkeypatch.setattr(systemd_backend, "PACKAGED_UNIT_PATH", current_unit)
    monkeypatch.setattr(systemd_backend, "DEFAULT_SYSTEMD_ENV_DIR", compatibility_env_dir)
    monkeypatch.setattr(systemd_backend, "resolve_agsekit_bin", lambda: Path("/opt/new-agsekit/bin/agsekit"))

    def fake_run_systemctl(command, *, announce=True):
        commands.append((command, announce))
        if command[:3] == ["systemctl", "--user", "link"]:
            if linked_unit.exists() or linked_unit.is_symlink():
                linked_unit.unlink()
            linked_unit.symlink_to(Path(command[3]))

    monkeypatch.setattr(systemd_backend, "run_systemctl", fake_run_systemctl)

    systemd_backend.install_portforward_service(config_path, project_dir=current_project, announce=False)

    assert linked_unit.resolve() == current_unit.resolve()
    assert commands == [
        (["systemctl", "--user", "link", str(current_unit)], False),
        (["systemctl", "--user", "daemon-reload"], False),
        (["systemctl", "--user", "restart", systemd_backend.SERVICE_NAME], False),
        (["systemctl", "--user", "enable", systemd_backend.SERVICE_NAME], False),
    ]
    written_env = (env_dir / systemd_backend.ENV_FILENAME).read_text(encoding="utf-8")
    assert "AGSEKIT_BIN=/opt/new-agsekit/bin/agsekit" in written_env
    assert f"AGSEKIT_CONFIG={config_path.resolve()}" in written_env
    assert f"AGSEKIT_PROJECT_DIR={current_project.resolve()}" in written_env
    compatibility_env = compatibility_env_dir / systemd_backend.ENV_FILENAME
    assert compatibility_env.is_symlink()
    assert compatibility_env.resolve() == (env_dir / systemd_backend.ENV_FILENAME).resolve()


def test_get_portforward_service_status_includes_show_data_and_logs(monkeypatch, tmp_path):
    linked_unit = tmp_path / "user-systemd" / "agsekit-portforward.service"
    linked_unit.parent.mkdir(parents=True)
    linked_unit.write_text("", encoding="utf-8")

    monkeypatch.setattr(systemd_backend, "LINKED_UNIT_PATH", linked_unit)
    monkeypatch.setattr(systemd_backend, "PACKAGED_UNIT_PATH", tmp_path / "pkg.service")
    (tmp_path / "pkg.service").write_text("[Unit]\nDescription=test\n", encoding="utf-8")

    def fake_query_systemctl(command):
        if command[:3] == ["systemctl", "--user", "is-enabled"]:
            return subprocess.CompletedProcess(command, 0, stdout="enabled\n", stderr="")
        if command[:3] == ["systemctl", "--user", "is-active"]:
            return subprocess.CompletedProcess(command, 0, stdout="active\n", stderr="")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "LoadState=loaded\n"
                "ActiveState=active\n"
                "SubState=running\n"
                "MainPID=5678\n"
                "FragmentPath=/home/test/.config/systemd/user/agsekit-portforward.service\n"
                "Result=success\n"
                "ActiveEnterTimestamp=Sun 2026-03-29 10:00:00 +07\n"
                "InactiveEnterTimestamp=Sun 2026-03-29 09:00:00 +07\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(systemd_backend, "query_systemctl", fake_query_systemctl)
    monkeypatch.setattr(
        systemd_backend,
        "query_journalctl",
        lambda command: subprocess.CompletedProcess(
            command,
            0,
            stdout="2026-03-29T10:00:00+07:00 line1\n2026-03-29T10:01:00+07:00 line2\n",
            stderr="",
        ),
    )

    status = systemd_backend.get_portforward_service_status()
    lines = systemd_backend.render_status_lines(status)

    assert status.installed is True
    assert status.enabled == "enabled"
    assert status.active == "active"
    assert status.load == "loaded"
    assert status.substate == "running"
    assert status.main_pid == "5678"
    assert status.result == "success"
    assert any("Recent logs:" in line for line in lines)
    assert any("line2" in line for line in lines)


def test_systemd_alias_warns_and_delegates_to_daemon(monkeypatch, tmp_path):
    calls = []
    config_path = tmp_path / "config.yaml"
    config_path.write_text("vms: {}\n", encoding="utf-8")

    monkeypatch.setattr(daemon_module, "run_daemon_install", lambda config_path, *, debug: calls.append((config_path, debug)))

    runner = CliRunner()
    result = runner.invoke(systemd_alias_module.systemd_group, ["install", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [(str(config_path), False)]
    assert "deprecated" in result.output.lower()
    assert "agsekit daemon install" in result.output


def test_systemd_alias_status_warns_and_delegates(monkeypatch):
    calls = []
    monkeypatch.setattr(daemon_module, "run_daemon_status", lambda: calls.append("status"))

    runner = CliRunner()
    result = runner.invoke(systemd_alias_module.systemd_group, ["status"])

    assert result.exit_code == 0
    assert calls == ["status"]
    assert "deprecated" in result.output.lower()
