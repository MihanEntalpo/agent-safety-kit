import sys
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.prepare as prepare_module
import agsekit_cli.vm_prepare as vm_prepare_module
from agsekit_cli.commands.prepare import prepare_command


def test_prepare_logs_existing_ssh_keypair(monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    ssh_dir = home / ".config" / "agsekit" / "ssh"
    ssh_dir.mkdir(parents=True)
    (ssh_dir / "id_rsa").write_text("private", encoding="utf-8")
    (ssh_dir / "id_rsa.pub").write_text("public", encoding="utf-8")

    monkeypatch.setattr(vm_prepare_module.Path, "home", lambda: home)

    vm_prepare_module.ensure_host_ssh_keypair()

    captured = capsys.readouterr()
    assert f"SSH keypair already exists at {ssh_dir}, reusing." in captured.out


def test_prepare_command_installs_dependencies_and_keys(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(prepare_module, "_install_multipass", lambda: calls.append("install"))
    monkeypatch.setattr(prepare_module, "ensure_host_ssh_keypair", lambda: calls.append("keys"))

    runner = CliRunner()
    result = runner.invoke(prepare_command, [])

    assert result.exit_code == 0
    assert calls == ["install", "keys"]
