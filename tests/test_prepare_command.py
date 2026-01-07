import json
import sys
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.prepare as prepare_module
from agsekit_cli.commands.prepare import prepare_command


def _write_config(config_path: Path, vm_names: list[str]) -> None:
    entries = "\n".join(f"  {name}:\n    cpu: 1\n    ram: 1G\n    disk: 5G" for name in vm_names)
    config_path.write_text(f"vms:\n{entries}\n", encoding="utf-8")


def test_prepare_logs_existing_ssh_keypair(monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    ssh_dir = home / ".config" / "agsekit" / "ssh"
    ssh_dir.mkdir(parents=True)
    (ssh_dir / "id_rsa").write_text("private", encoding="utf-8")
    (ssh_dir / "id_rsa.pub").write_text("public", encoding="utf-8")

    monkeypatch.setattr(prepare_module.Path, "home", lambda: home)

    prepare_module._ensure_host_ssh_keypair()

    captured = capsys.readouterr()
    assert f"SSH keypair already exists at {ssh_dir}, reusing." in captured.out


def test_prepare_command_runs_vm_steps_and_logs(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["vm1"])

    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    private_key = key_dir / "id_rsa"
    public_key = key_dir / "id_rsa.pub"
    private_key.write_text("private-key", encoding="utf-8")
    public_key.write_text("public-key", encoding="utf-8")

    calls: list[list[str]] = []

    class Result:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(command, description, capture_output=True):
        calls.append(command)
        command_tail = command[-1] if command else ""

        if command[:2] == ["multipass", "start"]:
            return Result(0)
        if "dpkg -s git proxychains4" in command_tail:
            return Result(1)
        if "apt-get install -y git proxychains4" in command_tail:
            return Result(0)
        if "sudo install -d -m 700" in command_tail:
            return Result(0)
        if "sudo cat /home/ubuntu/.ssh/id_rsa" in command_tail:
            return Result(1)
        if "sudo cat /home/ubuntu/.ssh/id_rsa.pub" in command_tail:
            return Result(1)
        if command[:2] == ["multipass", "transfer"]:
            return Result(0)
        if "sudo chown ubuntu:ubuntu /home/ubuntu/.ssh/id_rsa" in command_tail:
            return Result(0)
        if "authorized_keys" in command_tail:
            return Result(0)

        return Result(0)

    monkeypatch.setattr(prepare_module, "_install_multipass", lambda: None)
    monkeypatch.setattr(prepare_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        prepare_module,
        "fetch_existing_info",
        lambda: json.dumps({"list": [{"name": "vm1"}]}),
    )
    monkeypatch.setattr(prepare_module, "_run_multipass", fake_run)
    monkeypatch.setattr(prepare_module, "_ensure_host_ssh_keypair", lambda: (private_key, public_key))

    runner = CliRunner()
    result = runner.invoke(prepare_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert "Preparing VM vm1" in result.output
    assert "Installing git and proxychains4 in vm1." in result.output
    assert "Syncing SSH keys into vm1 for user ubuntu." in result.output
    assert any(command[:2] == ["multipass", "start"] for command in calls)
    assert any("apt-get install -y git proxychains4" in command[-1] for command in calls)
    assert any(command[:2] == ["multipass", "transfer"] for command in calls)
