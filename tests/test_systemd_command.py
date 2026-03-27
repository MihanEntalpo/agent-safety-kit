from pathlib import Path

import agsekit_cli.commands.systemd as systemd_module


def test_install_portforward_service_relinks_existing_unit_to_current_installation(monkeypatch, tmp_path):
    current_project = tmp_path / "current"
    current_unit = current_project / "systemd" / "agsekit-portforward.service"
    current_unit.parent.mkdir(parents=True)
    current_unit.write_text("[Unit]\nDescription=current\n", encoding="utf-8")

    old_project = tmp_path / "old"
    old_unit = old_project / "systemd" / "agsekit-portforward.service"
    old_unit.parent.mkdir(parents=True)
    old_unit.write_text("[Unit]\nDescription=old\n", encoding="utf-8")

    linked_unit = tmp_path / "user-systemd" / "agsekit-portforward.service"
    linked_unit.parent.mkdir(parents=True)
    linked_unit.symlink_to(old_unit)

    config_path = tmp_path / "config.yaml"
    config_path.write_text("vms: {}\n", encoding="utf-8")

    env_path = tmp_path / "agsekit-config" / "config.yaml"
    commands = []

    monkeypatch.setattr(systemd_module, "LINKED_UNIT_PATH", linked_unit)
    monkeypatch.setattr(systemd_module, "DEFAULT_CONFIG_PATH", env_path)
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
    written_env = (env_path.parent / systemd_module.ENV_FILENAME).read_text(encoding="utf-8")
    assert "AGSEKIT_BIN=/opt/new-agsekit/bin/agsekit" in written_env
    assert f"AGSEKIT_CONFIG={config_path.resolve()}" in written_env
    assert f"AGSEKIT_PROJECT_DIR={current_project.resolve()}" in written_env
