import subprocess
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

import agsekit_cli.commands.systemd as systemd_module


def test_packaged_systemd_unit_uses_shell_wrapper_for_env_expansion():
    unit_path = Path("agsekit_cli/systemd/agsekit-portforward.service")
    contents = unit_path.read_text(encoding="utf-8")

    assert 'ExecStart=/bin/bash -lc \'exec "$AGSEKIT_BIN" portforward --config "$AGSEKIT_CONFIG"\'' in contents


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
    config_path.write_text(
        f"global:\n  systemd_env_folder: {env_dir}\nvms: {{}}\n",
        encoding="utf-8",
    )
    commands = []

    monkeypatch.setattr(systemd_module, "LINKED_UNIT_PATH", linked_unit)
    monkeypatch.setattr(systemd_module, "PACKAGED_UNIT_PATH", current_unit)
    monkeypatch.setattr(systemd_module, "DEFAULT_SYSTEMD_ENV_DIR", tmp_path / "compatibility-env")
    monkeypatch.setattr(systemd_module, "_resolve_agsekit_bin", lambda: Path("/opt/new-agsekit/bin/agsekit"))
    def fake_run_systemctl(command, *, announce=True):
        commands.append((command, announce))
        if command[:3] == ["systemctl", "--user", "link"]:
            if linked_unit.exists() or linked_unit.is_symlink():
                linked_unit.unlink()
            linked_unit.symlink_to(Path(command[3]))

    monkeypatch.setattr(systemd_module, "_run_systemctl", fake_run_systemctl)

    systemd_module.install_portforward_service(
        config_path,
        project_dir=current_project,
        announce=False,
    )

    assert linked_unit.resolve() == current_unit.resolve()
    assert commands == [
        (["systemctl", "--user", "link", str(current_unit)], False),
        (["systemctl", "--user", "daemon-reload"], False),
        (["systemctl", "--user", "restart", systemd_module.SERVICE_NAME], False),
        (["systemctl", "--user", "enable", systemd_module.SERVICE_NAME], False),
    ]
    written_env = (env_dir / systemd_module.ENV_FILENAME).read_text(encoding="utf-8")
    assert "AGSEKIT_BIN=/opt/new-agsekit/bin/agsekit" in written_env
    assert f"AGSEKIT_CONFIG={config_path.resolve()}" in written_env
    assert f"AGSEKIT_PROJECT_DIR={current_project.resolve()}" in written_env
    compatibility_env = systemd_module.DEFAULT_SYSTEMD_ENV_DIR / systemd_module.ENV_FILENAME
    assert compatibility_env.is_symlink()
    assert compatibility_env.resolve() == (env_dir / systemd_module.ENV_FILENAME).resolve()


def test_install_portforward_service_uses_packaged_unit_when_project_dir_has_no_unit(monkeypatch, tmp_path):
    packaged_unit = tmp_path / "site-packages" / "agsekit_cli" / "systemd" / "agsekit-portforward.service"
    packaged_unit.parent.mkdir(parents=True)
    packaged_unit.write_text("[Unit]\nDescription=packaged\n", encoding="utf-8")

    linked_unit = tmp_path / "user-systemd" / "agsekit-portforward.service"
    linked_unit.parent.mkdir(parents=True)

    config_path = tmp_path / "config.yaml"
    env_dir = tmp_path / "agsekit-config"
    config_path.write_text(
        f"global:\n  systemd_env_folder: {env_dir}\nvms: {{}}\n",
        encoding="utf-8",
    )
    commands = []

    monkeypatch.setattr(systemd_module, "LINKED_UNIT_PATH", linked_unit)
    monkeypatch.setattr(systemd_module, "PACKAGED_UNIT_PATH", packaged_unit)
    monkeypatch.setattr(systemd_module, "DEFAULT_SYSTEMD_ENV_DIR", tmp_path / "compatibility-env")
    monkeypatch.setattr(systemd_module, "_resolve_agsekit_bin", lambda: Path("/opt/agsekit/bin/agsekit"))

    def fake_run_systemctl(command, *, announce=True):
        commands.append((command, announce))
        if command[:3] == ["systemctl", "--user", "link"]:
            linked_unit.symlink_to(Path(command[3]))

    monkeypatch.setattr(systemd_module, "_run_systemctl", fake_run_systemctl)

    systemd_module.install_portforward_service(config_path, project_dir=tmp_path / "project", announce=False)

    assert linked_unit.resolve() == packaged_unit.resolve()
    assert commands[0] == (["systemctl", "--user", "link", str(packaged_unit)], False)


def test_systemd_status_command_prints_service_state(monkeypatch):
    monkeypatch.setattr(
        systemd_module,
        "get_portforward_service_status",
        lambda: systemd_module.SystemdServiceStatus(
            service="agsekit-portforward.service",
            unit_path="/opt/agsekit/agsekit_cli/systemd/agsekit-portforward.service",
            linked_unit="/home/test/.config/systemd/user/agsekit-portforward.service",
            installed=True,
            enabled="enabled",
            active="active",
            load="loaded",
            substate="running",
            main_pid="1234",
            fragment_path="/home/test/.config/systemd/user/agsekit-portforward.service",
            result="success",
            active_since="Sun 2026-03-29 10:00:00 +07",
            inactive_since="Sun 2026-03-29 09:58:00 +07",
            logs=["2026-03-29T10:00:00+07:00 started", "2026-03-29T10:00:03+07:00 healthy"],
        ),
    )

    runner = CliRunner()
    result = runner.invoke(systemd_module.systemd_group, ["status"])

    assert result.exit_code == 0
    assert "agsekit-portforward.service" in result.output
    assert "enabled" in result.output
    assert "active" in result.output
    assert "loaded" in result.output
    assert "running" in result.output
    assert "1234" in result.output
    assert "Recent logs:" in result.output
    assert "healthy" in result.output


def test_get_portforward_service_status_includes_show_data_and_logs(monkeypatch, tmp_path):
    linked_unit = tmp_path / "user-systemd" / "agsekit-portforward.service"
    linked_unit.parent.mkdir(parents=True)
    linked_unit.write_text("", encoding="utf-8")

    monkeypatch.setattr(systemd_module, "LINKED_UNIT_PATH", linked_unit)
    monkeypatch.setattr(systemd_module, "PACKAGED_UNIT_PATH", tmp_path / "pkg.service")
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

    monkeypatch.setattr(systemd_module, "_query_systemctl", fake_query_systemctl)
    monkeypatch.setattr(
        systemd_module,
        "_query_journalctl",
        lambda command: subprocess.CompletedProcess(
            command,
            0,
            stdout="2026-03-29T10:00:00+07:00 line1\n2026-03-29T10:01:00+07:00 line2\n",
            stderr="",
        ),
    )

    status = systemd_module.get_portforward_service_status()

    assert status.installed is True
    assert status.enabled == "enabled"
    assert status.active == "active"
    assert status.load == "loaded"
    assert status.substate == "running"
    assert status.main_pid == "5678"
    assert status.result == "success"
    assert status.logs == [
        "2026-03-29T10:00:00+07:00 line1",
        "2026-03-29T10:01:00+07:00 line2",
    ]


def test_systemd_status_skips_logs_when_service_not_installed(monkeypatch):
    monkeypatch.setattr(
        systemd_module,
        "get_portforward_service_status",
        lambda: systemd_module.SystemdServiceStatus(
            service="agsekit-portforward.service",
            unit_path="/opt/agsekit/agsekit_cli/systemd/agsekit-portforward.service",
            linked_unit="not linked",
            installed=False,
            enabled="disabled",
            active="inactive",
            load="not-found",
            substate="dead",
            main_pid="0",
            fragment_path="unknown",
            result="success",
            active_since="unknown",
            inactive_since="unknown",
            logs=[],
        ),
    )

    runner = CliRunner()
    result = runner.invoke(systemd_module.systemd_group, ["status"])

    assert result.exit_code == 0
    assert "Installed: no" in result.output
    assert "Recent logs are unavailable because the service is not installed." in result.output


def test_systemd_install_command_is_quiet_without_debug(monkeypatch, tmp_path):
    calls = []
    config_path = tmp_path / "config.yaml"
    config_path.write_text("vms: {}\n", encoding="utf-8")

    monkeypatch.setattr(
        systemd_module,
        "install_portforward_service",
        lambda config_path, project_dir=None, announce=True: calls.append(
            {
                "config_path": Path(config_path) if config_path else None,
                "project_dir": project_dir,
                "announce": announce,
            }
        ),
    )

    runner = CliRunner()
    result = runner.invoke(systemd_module.systemd_group, ["install", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [
        {
            "config_path": config_path,
            "project_dir": Path.cwd(),
            "announce": False,
        }
    ]
    assert result.output.splitlines() == [
        "Installing/updating systemd portforward service...",
        "Systemd portforward service installed successfully.",
    ]


def test_systemd_install_command_shows_verbose_output_in_debug(monkeypatch, tmp_path):
    calls = []
    config_path = tmp_path / "config.yaml"
    config_path.write_text("vms: {}\n", encoding="utf-8")

    monkeypatch.setattr(
        systemd_module,
        "install_portforward_service",
        lambda config_path, project_dir=None, announce=True: calls.append(
            {
                "config_path": Path(config_path) if config_path else None,
                "project_dir": project_dir,
                "announce": announce,
            }
        ),
    )

    runner = CliRunner()
    result = runner.invoke(systemd_module.systemd_group, ["install", "--config", str(config_path), "--debug"])

    assert result.exit_code == 0
    assert calls == [
        {
            "config_path": config_path,
            "project_dir": Path.cwd(),
            "announce": True,
        }
    ]
    assert "Installing/updating systemd portforward service..." not in result.output


def test_systemd_uninstall_command_is_quiet_without_debug(monkeypatch):
    calls = []

    monkeypatch.setattr(
        systemd_module,
        "uninstall_portforward_service",
        lambda project_dir=None, announce=True: calls.append(
            {
                "project_dir": project_dir,
                "announce": announce,
            }
        ),
    )

    runner = CliRunner()
    result = runner.invoke(systemd_module.systemd_group, ["uninstall"])

    assert result.exit_code == 0
    assert calls == [
        {
            "project_dir": Path.cwd(),
            "announce": False,
        }
    ]
    assert result.output.splitlines() == [
        "Removing systemd portforward service...",
        "Systemd portforward service removed successfully.",
    ]


def test_systemd_uninstall_command_shows_verbose_output_in_debug(monkeypatch):
    calls = []

    monkeypatch.setattr(
        systemd_module,
        "uninstall_portforward_service",
        lambda project_dir=None, announce=True: calls.append(
            {
                "project_dir": project_dir,
                "announce": announce,
            }
        ),
    )

    runner = CliRunner()
    result = runner.invoke(systemd_module.systemd_group, ["uninstall", "--debug"])

    assert result.exit_code == 0
    assert calls == [
        {
            "project_dir": Path.cwd(),
            "announce": True,
        }
    ]
    assert "Removing systemd portforward service..." not in result.output


def test_manage_portforward_service_runs_requested_systemctl_action(monkeypatch, tmp_path):
    linked_unit = tmp_path / "user-systemd" / "agsekit-portforward.service"
    linked_unit.parent.mkdir(parents=True)
    linked_unit.write_text("", encoding="utf-8")

    commands = []
    monkeypatch.setattr(systemd_module, "LINKED_UNIT_PATH", linked_unit)
    monkeypatch.setattr(systemd_module, "_run_systemctl", lambda command, *, announce=True: commands.append((command, announce)))

    systemd_module.manage_portforward_service("restart", announce=False)

    assert commands == [(["systemctl", "--user", "restart", systemd_module.SERVICE_NAME], False)]


def test_manage_portforward_service_requires_installed_service(monkeypatch, tmp_path):
    monkeypatch.setattr(systemd_module, "LINKED_UNIT_PATH", tmp_path / "missing.service")

    with pytest.raises(click.ClickException) as exc_info:
        systemd_module.manage_portforward_service("start", announce=False)

    assert str(exc_info.value) == "Systemd portforward service is not installed."


def test_systemd_start_command_is_quiet_without_debug(monkeypatch):
    calls = []

    monkeypatch.setattr(systemd_module, "manage_portforward_service", lambda action, *, announce=True: calls.append((action, announce)))

    runner = CliRunner()
    result = runner.invoke(systemd_module.systemd_group, ["start"])

    assert result.exit_code == 0
    assert calls == [("start", False)]
    assert result.output.splitlines() == [
        "Starting systemd portforward service...",
        "Systemd portforward service started successfully.",
    ]


def test_systemd_stop_command_is_quiet_without_debug(monkeypatch):
    calls = []

    monkeypatch.setattr(systemd_module, "manage_portforward_service", lambda action, *, announce=True: calls.append((action, announce)))

    runner = CliRunner()
    result = runner.invoke(systemd_module.systemd_group, ["stop"])

    assert result.exit_code == 0
    assert calls == [("stop", False)]
    assert result.output.splitlines() == [
        "Stopping systemd portforward service...",
        "Systemd portforward service stopped successfully.",
    ]


def test_systemd_restart_command_is_quiet_without_debug(monkeypatch):
    calls = []

    monkeypatch.setattr(systemd_module, "manage_portforward_service", lambda action, *, announce=True: calls.append((action, announce)))

    runner = CliRunner()
    result = runner.invoke(systemd_module.systemd_group, ["restart"])

    assert result.exit_code == 0
    assert calls == [("restart", False)]
    assert result.output.splitlines() == [
        "Restarting systemd portforward service...",
        "Systemd portforward service restarted successfully.",
    ]


def test_systemd_service_management_commands_show_verbose_output_in_debug(monkeypatch):
    calls = []

    monkeypatch.setattr(systemd_module, "manage_portforward_service", lambda action, *, announce=True: calls.append((action, announce)))

    runner = CliRunner()

    start_result = runner.invoke(systemd_module.systemd_group, ["start", "--debug"])
    stop_result = runner.invoke(systemd_module.systemd_group, ["stop", "--debug"])
    restart_result = runner.invoke(systemd_module.systemd_group, ["restart", "--debug"])

    assert start_result.exit_code == 0
    assert stop_result.exit_code == 0
    assert restart_result.exit_code == 0
    assert calls == [("start", True), ("stop", True), ("restart", True)]
    assert "Starting systemd portforward service..." not in start_result.output
    assert "Stopping systemd portforward service..." not in stop_result.output
    assert "Restarting systemd portforward service..." not in restart_result.output
