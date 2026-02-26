import sys
from pathlib import Path

from click.testing import CliRunner
import pytest

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
    monkeypatch.setattr(prepare_module, "_install_ansible_collection", lambda: calls.append("ansible"))
    monkeypatch.setattr(prepare_module, "ensure_host_ssh_keypair", lambda: calls.append("keys"))

    runner = CliRunner()
    result = runner.invoke(prepare_command, [])

    assert result.exit_code == 0
    assert calls == ["install", "ansible", "keys"]


def test_install_multipass_prefers_arch_over_debian(monkeypatch):
    calls: list[str] = []

    def fake_which(binary: str):
        if binary == "multipass":
            return None
        if binary == "pacman":
            return "/usr/bin/pacman"
        if binary == "apt-get":
            return "/usr/bin/apt-get"
        return None

    monkeypatch.setattr(prepare_module.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_module, "_install_multipass_arch", lambda: calls.append("arch"))
    monkeypatch.setattr(prepare_module, "_install_multipass_debian", lambda: calls.append("debian"))

    prepare_module._install_multipass()

    assert calls == ["arch"]


def test_install_multipass_uses_debian_when_pacman_absent(monkeypatch):
    calls: list[str] = []

    def fake_which(binary: str):
        if binary == "multipass":
            return None
        if binary == "pacman":
            return None
        if binary == "apt-get":
            return "/usr/bin/apt-get"
        return None

    monkeypatch.setattr(prepare_module.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_module, "_install_multipass_arch", lambda: calls.append("arch"))
    monkeypatch.setattr(prepare_module, "_install_multipass_debian", lambda: calls.append("debian"))

    prepare_module._install_multipass()

    assert calls == ["debian"]


def test_install_multipass_arch_requires_aur_helper(monkeypatch):
    monkeypatch.setattr(prepare_module.shutil, "which", lambda _binary: None)

    with pytest.raises(prepare_module.click.ClickException) as exc_info:
        prepare_module._install_multipass_arch()

    assert "AUR helper" in str(exc_info.value)


def test_install_multipass_arch_uses_yay(monkeypatch):
    commands: list[list[str]] = []

    def fake_which(binary: str):
        if binary == "yay":
            return "/usr/bin/yay"
        if binary == "aura":
            return None
        return None

    def fake_run(command, check):
        commands.append(command)
        assert check is True

    monkeypatch.setattr(prepare_module.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_module.subprocess, "run", fake_run)

    prepare_module._install_multipass_arch()

    assert commands == [["yay", "-S", "--noconfirm", "multipass", "libvirt", "dnsmasq", "qemu-base"]]
