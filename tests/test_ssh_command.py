from pathlib import Path

from click.testing import CliRunner

import agsekit_cli.commands.ssh as ssh_module


def test_ssh_command_uses_custom_ssh_keys_folder(monkeypatch, tmp_path):
    ssh_dir = tmp_path / "custom-ssh"
    ssh_dir.mkdir()
    private_key = ssh_dir / "id_rsa"
    private_key.write_text("private", encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"global:\n  ssh_keys_folder: {ssh_dir}\nvms:\n  agent:\n    cpu: 1\n    ram: 1G\n    disk: 5G\n",
        encoding="utf-8",
    )

    commands = []

    monkeypatch.setattr(ssh_module, "host_tool_exists", lambda binary: binary == "ssh")
    monkeypatch.setattr(ssh_module, "resolved_ssh_command", lambda: "ssh")
    monkeypatch.setattr(ssh_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(ssh_module, "_fetch_vm_ip", lambda vm_name, debug=False: "10.0.0.8")
    monkeypatch.setattr(
        ssh_module,
        "_run_ssh_process",
        lambda command, debug=False: commands.append((command, debug)) or 0,
    )

    runner = CliRunner()
    result = runner.invoke(ssh_module.ssh_command, ["--config", str(config_path), "agent", "-N"])

    assert result.exit_code == 0
    assert commands == [(["ssh", "-i", str(private_key), "-N", "ubuntu@10.0.0.8"], False)]
