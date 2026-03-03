import json
import sys
from pathlib import Path

from click.testing import CliRunner
import pytest
import yaml

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


def test_prepare_vm_packages_installs_proxychains_runner_scripts():
    playbook_path = Path("agsekit_cli/ansible/vm_packages.yml")
    playbook = yaml.safe_load(playbook_path.read_text(encoding="utf-8"))
    tasks = playbook[1]["tasks"]

    common_task = next(item for item in tasks if item["name"] == "Install agsekit proxychains common script")
    common_copy = common_task["ansible.builtin.copy"]
    assert common_copy["src"] == "{{ playbook_dir }}/../agent_scripts/proxychains_common.sh"
    assert common_copy["dest"] == "/usr/bin/proxychains_common.sh"
    assert common_copy["mode"] == "0644"

    runner_task = next(item for item in tasks if item["name"] == "Install agsekit proxychains runner script")
    runner_copy = runner_task["ansible.builtin.copy"]
    assert runner_copy["src"] == "{{ playbook_dir }}/../run_with_proxychains.sh"
    assert runner_copy["dest"] == "/usr/bin/agsekit-run_with_proxychains.sh"
    assert runner_copy["mode"] == "0755"


def test_prepare_vm_ssh_playbook_manages_authorized_keys_and_known_hosts():
    playbook_path = Path("agsekit_cli/ansible/vm_ssh.yml")
    playbook = yaml.safe_load(playbook_path.read_text(encoding="utf-8"))

    register_tasks = playbook[0]["tasks"]
    register_task = next(item for item in register_tasks if item["name"] == "Register Multipass VM")
    add_host = register_task["ansible.builtin.add_host"]
    assert add_host["ansible_connection"] == "theko2fi.multipass.multipass"

    vm_sync_tasks = playbook[1]["tasks"]
    key_task = next(item for item in vm_sync_tasks if item["name"] == "Ensure VM authorized_keys contains host key")
    lineinfile = key_task["ansible.builtin.lineinfile"]
    assert lineinfile["path"] == "{{ vm_home }}/.ssh/authorized_keys"
    assert lineinfile["line"] == "{{ host_public_key }}"
    assert lineinfile["mode"] == "0600"

    local_sync_play = playbook[2]
    assert local_sync_play["hosts"] == "localhost"
    assert local_sync_play["connection"] == "local"
    local_sync_tasks = local_sync_play["tasks"]

    known_hosts_task = next(item for item in local_sync_tasks if item["name"] == "Ensure VM host keys in local known_hosts")
    known_hosts = known_hosts_task["ansible.builtin.known_hosts"]
    assert known_hosts["path"] == "{{ known_hosts_path }}"
    assert known_hosts["hash_host"] is True


def test_ensure_vm_ssh_access_runs_ansible_playbook(monkeypatch, tmp_path):
    public_key = tmp_path / "id_rsa.pub"
    public_key.write_text("ssh-rsa AAAAB3Nza test@example\n", encoding="utf-8")
    calls: list[list[str]] = []

    class Result:
        returncode = 0

    def fake_run(command, check=False, capture_output=False, text=False):
        del check, capture_output, text
        calls.append(command)
        return Result()

    monkeypatch.setattr(vm_prepare_module.subprocess, "run", fake_run)

    vm_prepare_module._ensure_vm_ssh_access("agent", public_key, ["agent", "10.0.0.15", ""])

    assert len(calls) == 1
    command = calls[0]
    assert command[:3] == ["ansible-playbook", "-i", "localhost,"]
    assert command[-1].endswith("/ansible/vm_ssh.yml")

    payload = json.loads(command[command.index("-e") + 1])
    assert payload["vm_name"] == "agent"
    assert payload["host_public_key"] == "ssh-rsa AAAAB3Nza test@example"
    assert payload["vm_known_hosts"] == ["agent", "10.0.0.15"]
