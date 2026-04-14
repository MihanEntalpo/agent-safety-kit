import json
import sys
from pathlib import Path
from typing import Optional

from click.testing import CliRunner
import pytest
import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib

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
    (ssh_dir / "id_rsa.pub").write_text("ssh-rsa AAAA expected@example\n", encoding="utf-8")

    monkeypatch.setattr(vm_prepare_module.Path, "home", lambda: home)
    monkeypatch.setattr(vm_prepare_module, "_derive_public_key", lambda _path: "ssh-rsa AAAA expected@example")

    vm_prepare_module.ensure_host_ssh_keypair()

    captured = capsys.readouterr()
    assert f"SSH keypair already exists at {ssh_dir}, reusing." in captured.out


def test_prepare_repairs_mismatched_public_key(monkeypatch, tmp_path):
    home = tmp_path / "home"
    ssh_dir = home / ".config" / "agsekit" / "ssh"
    ssh_dir.mkdir(parents=True)
    private_key = ssh_dir / "id_rsa"
    public_key = ssh_dir / "id_rsa.pub"
    private_key.write_text("private", encoding="utf-8")
    public_key.write_text("ssh-rsa AAAA stale@example\n", encoding="utf-8")

    monkeypatch.setattr(vm_prepare_module.Path, "home", lambda: home)
    monkeypatch.setattr(vm_prepare_module, "_derive_public_key", lambda path: f"ssh-rsa AAAA {path.name}@current")

    returned_private, returned_public = vm_prepare_module.ensure_host_ssh_keypair()

    assert returned_private == private_key
    assert returned_public == public_key
    assert public_key.read_text(encoding="utf-8") == "ssh-rsa AAAA id_rsa@current\n"


def test_prepare_command_installs_dependencies_and_keys(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(prepare_module, "_install_multipass", lambda **kwargs: calls.append("install"))
    monkeypatch.setattr(prepare_module, "_ensure_ssh_keygen", lambda **kwargs: calls.append("ssh-keygen"))
    monkeypatch.setattr(prepare_module, "_ensure_rsync", lambda **kwargs: calls.append("rsync"))
    monkeypatch.setattr(prepare_module, "ensure_host_ssh_keypair", lambda *args, **kwargs: calls.append("keys"))

    runner = CliRunner()
    result = runner.invoke(prepare_command, [])

    assert result.exit_code == 0
    assert calls == ["install", "ssh-keygen", "rsync", "keys"]


def test_run_prepare_uses_ssh_keys_folder_from_main_config(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    ssh_dir = tmp_path / "custom-ssh"
    config_path.write_text(
        f"global:\n  ssh_keys_folder: {ssh_dir}\nvms:\n  agent:\n    cpu: 1\n    ram: 1G\n    disk: 5G\n",
        encoding="utf-8",
    )
    captured = {}

    monkeypatch.setattr(prepare_module, "_prepare_host_dependencies", lambda **kwargs: None)
    monkeypatch.setattr(
        prepare_module,
        "ensure_host_ssh_keypair",
        lambda *args, **kwargs: captured.update(kwargs),
    )

    prepare_module.run_prepare(debug=False, config_path=str(config_path))

    assert captured["ssh_dir"] == ssh_dir.resolve()
    assert captured["verbose"] is False


def test_run_prepare_suppresses_multipass_echo_when_progress_enabled(monkeypatch, capsys):
    calls: list[bool] = []

    monkeypatch.setattr(
        prepare_module.shutil,
        "which",
        lambda binary: "/usr/bin/{0}".format(binary) if binary in {"multipass", "ssh-keygen", "rsync"} else None,
    )
    monkeypatch.setattr(prepare_module, "ensure_host_ssh_keypair", lambda *args, **kwargs: None)

    class DummyProgress:
        def __bool__(self):
            return True

        def update(self, *args, **kwargs):
            del args, kwargs

        def advance(self, *args, **kwargs):
            del args, kwargs

    original = prepare_module._install_multipass

    def wrapped_install_multipass(*, quiet: bool = False):
        calls.append(quiet)
        return original(quiet=quiet)

    monkeypatch.setattr(prepare_module, "_install_multipass", wrapped_install_multipass)

    prepare_module.run_prepare(debug=False, progress=DummyProgress())

    captured = capsys.readouterr()
    assert calls == [True]
    assert "Multipass already installed" not in captured.out


def test_run_prepare_suspends_progress_during_multipass_install(monkeypatch):
    calls: list[str] = []

    class DummySuspend:
        def __enter__(self):
            calls.append("enter")
            return None

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback
            calls.append("exit")
            return None

    class DummyProgress:
        def __bool__(self):
            return True

        def update(self, *args, **kwargs):
            del args, kwargs

        def advance(self, *args, **kwargs):
            del args, kwargs

        def suspend(self):
            calls.append("suspend")
            return DummySuspend()

    monkeypatch.setattr(prepare_module, "_install_multipass", lambda **kwargs: calls.append(f"install:{kwargs['quiet']}"))
    monkeypatch.setattr(prepare_module, "_ensure_ssh_keygen", lambda **kwargs: calls.append(f"ssh-keygen:{kwargs['quiet']}"))
    monkeypatch.setattr(prepare_module, "_ensure_rsync", lambda **kwargs: calls.append(f"rsync:{kwargs['quiet']}"))
    monkeypatch.setattr(prepare_module, "ensure_host_ssh_keypair", lambda *args, **kwargs: None)

    prepare_module.run_prepare(debug=False, progress=DummyProgress())

    assert calls == ["suspend", "enter", "install:True", "ssh-keygen:True", "rsync:True", "exit"]


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
    monkeypatch.setattr(prepare_module, "_install_multipass_arch", lambda **kwargs: calls.append("arch"))
    monkeypatch.setattr(prepare_module, "_install_multipass_debian", lambda **kwargs: calls.append("debian"))

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
    monkeypatch.setattr(prepare_module, "_install_multipass_arch", lambda **kwargs: calls.append("arch"))
    monkeypatch.setattr(prepare_module, "_install_multipass_debian", lambda **kwargs: calls.append("debian"))

    prepare_module._install_multipass()

    assert calls == ["debian"]


def test_install_multipass_does_not_try_to_install_inside_wsl(monkeypatch):
    monkeypatch.setattr(prepare_module.shutil, "which", lambda _binary: None)
    monkeypatch.setattr(prepare_module, "_is_wsl", lambda: True)
    monkeypatch.setattr(
        prepare_module,
        "_install_multipass_debian",
        lambda **_kwargs: pytest.fail("Debian installer must not run in WSL"),
    )
    monkeypatch.setattr(
        prepare_module,
        "_install_multipass_arch",
        lambda **_kwargs: pytest.fail("Arch installer must not run in WSL"),
    )
    monkeypatch.setattr(
        prepare_module,
        "_install_multipass_brew",
        lambda **_kwargs: pytest.fail("Homebrew installer must not run in WSL"),
    )

    with pytest.raises(prepare_module.click.ClickException) as exc_info:
        prepare_module._install_multipass()

    assert "WSL detected" in str(exc_info.value)


def test_install_multipass_skips_installation_when_available_in_wsl(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(prepare_module.shutil, "which", lambda binary: "/usr/local/bin/multipass" if binary == "multipass" else None)
    monkeypatch.setattr(prepare_module, "_is_wsl", lambda: True)
    monkeypatch.setattr(prepare_module, "_install_multipass_debian", lambda **_kwargs: calls.append("debian"))

    prepare_module._install_multipass()

    assert calls == []


def test_install_multipass_uses_homebrew_on_macos(monkeypatch):
    calls: list[str] = []

    def fake_which(binary: str):
        if binary == "multipass":
            return None
        if binary == "pacman":
            return None
        if binary == "apt-get":
            return None
        if binary == "brew":
            return "/opt/homebrew/bin/brew"
        return None

    monkeypatch.setattr(prepare_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(prepare_module.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_module, "_install_multipass_arch", lambda **kwargs: calls.append("arch"))
    monkeypatch.setattr(prepare_module, "_install_multipass_debian", lambda **kwargs: calls.append("debian"))
    monkeypatch.setattr(prepare_module, "_install_multipass_brew", lambda **kwargs: calls.append("brew"))

    prepare_module._install_multipass()

    assert calls == ["brew"]


def test_install_multipass_arch_requires_aur_helper(monkeypatch):
    monkeypatch.setattr(prepare_module.shutil, "which", lambda _binary: None)

    with pytest.raises(prepare_module.click.ClickException) as exc_info:
        prepare_module._install_multipass_arch()

    assert "AUR helper" in str(exc_info.value)


def test_install_multipass_brew_uses_brew_install(monkeypatch):
    commands: list[list[str]] = []

    def fake_run(command, check):
        commands.append(command)
        assert check is True

    monkeypatch.setattr(prepare_module.subprocess, "run", fake_run)

    prepare_module._install_multipass_brew()

    assert commands == [["brew", "install", "multipass"]]


def test_ensure_rsync_installs_via_homebrew_on_macos(monkeypatch):
    commands: list[list[str]] = []
    installed = False

    def fake_which(binary: str):
        if binary == "rsync":
            return "/opt/homebrew/bin/rsync" if installed else None
        if binary == "brew":
            return "/opt/homebrew/bin/brew"
        return None

    def fake_run(command, check):
        nonlocal installed
        commands.append(command)
        assert check is True
        installed = True

    monkeypatch.setattr(prepare_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(prepare_module.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_module.subprocess, "run", fake_run)

    prepare_module._ensure_rsync()

    assert commands == [["brew", "install", "rsync"]]


def test_ensure_rsync_skips_homebrew_when_available_on_macos(monkeypatch):
    commands: list[list[str]] = []

    def fake_which(binary: str):
        if binary == "rsync":
            return "/usr/bin/rsync"
        if binary == "brew":
            return "/opt/homebrew/bin/brew"
        return None

    monkeypatch.setattr(prepare_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(prepare_module.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_module.subprocess, "run", lambda command, check: commands.append(command))

    prepare_module._ensure_rsync()

    assert commands == []


def test_ensure_rsync_installs_linux_package_when_missing(monkeypatch):
    calls: list[list[str]] = []
    installed = False

    def fake_which(binary: str):
        if binary == "rsync":
            return "/usr/bin/rsync" if installed else None
        if binary == "apt-get":
            return "/usr/bin/apt-get"
        return None

    def fake_install(packages, **_kwargs):
        nonlocal installed
        calls.append(packages)
        installed = True

    monkeypatch.setattr(prepare_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(prepare_module.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_module, "_install_debian_packages_if_missing", fake_install)

    prepare_module._ensure_rsync()

    assert calls == [["rsync"]]


def test_install_multipass_debian_installs_only_missing_host_packages(monkeypatch):
    commands: list[list[str]] = []

    monkeypatch.setattr(prepare_module, "_debian_package_installed", lambda package: package != "snapd")
    monkeypatch.setattr(prepare_module.shutil, "which", lambda binary: "/usr/bin/snap" if binary == "snap" else None)

    def fake_run(command, check, env=None):
        del env
        commands.append(command)
        assert check is True

    monkeypatch.setattr(prepare_module.subprocess, "run", fake_run)

    prepare_module._install_multipass_debian()

    assert commands == [
        ["sudo", "apt-get", "update"],
        ["sudo", "apt-get", "install", "-y", "snapd"],
        ["sudo", "snap", "install", "multipass", "--classic"],
    ]


def test_install_multipass_debian_skips_package_install_when_packages_exist(monkeypatch):
    commands: list[list[str]] = []

    monkeypatch.setattr(prepare_module, "_debian_package_installed", lambda _package: True)
    monkeypatch.setattr(prepare_module.shutil, "which", lambda binary: "/usr/bin/snap" if binary == "snap" else None)

    def fake_run(command, check, env=None):
        del env
        commands.append(command)
        assert check is True

    monkeypatch.setattr(prepare_module.subprocess, "run", fake_run)

    prepare_module._install_multipass_debian()

    assert commands == [["sudo", "snap", "install", "multipass", "--classic"]]


def test_package_data_includes_http_proxy_runner_script():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["agsekit_cli"]

    assert "run_with_http_proxy.sh" in package_data


def test_manifest_includes_http_proxy_runner_script():
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")

    assert "include agsekit_cli/run_with_http_proxy.sh" in manifest


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

    package_task = next(item for item in tasks if item["name"] == "Install base packages")
    packages = package_task["ansible.builtin.apt"]["name"]
    assert {"7zip", "git", "gzip", "privoxy", "proxychains4", "ripgrep", "zip", "zstd"}.issubset(set(packages))

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

    http_runner_task = next(item for item in tasks if item["name"] == "Install agsekit HTTP proxy runner script")
    http_runner_copy = http_runner_task["ansible.builtin.copy"]
    assert http_runner_copy["src"] == "{{ playbook_dir }}/../run_with_http_proxy.sh"
    assert http_runner_copy["dest"] == "/usr/bin/agsekit-run_with_http_proxy.sh"
    assert http_runner_copy["mode"] == "0755"


def test_prepare_vm_ssh_playbook_manages_authorized_keys_and_known_hosts():
    playbook_path = Path("agsekit_cli/ansible/vm_ssh.yml")
    playbook = yaml.safe_load(playbook_path.read_text(encoding="utf-8"))

    register_tasks = playbook[0]["tasks"]
    register_task = next(item for item in register_tasks if item["name"] == "Register Multipass VM")
    add_host = register_task["ansible.builtin.add_host"]
    assert add_host["ansible_connection"] == "agsekit_multipass"

    vm_sync_tasks = playbook[1]["tasks"]
    key_task = next(item for item in vm_sync_tasks if item["name"] == "Ensure VM authorized_keys contains host key")
    lineinfile = key_task["ansible.builtin.lineinfile"]
    assert lineinfile["path"] == "{{ vm_home }}/.ssh/authorized_keys"
    assert lineinfile["line"] == "{{ host_public_key }}"
    assert lineinfile["mode"] == "0600"

    local_sync_play = playbook[2]
    assert local_sync_play["hosts"] == "localhost"
    assert local_sync_play["connection"] == "local"
    assert local_sync_play["vars"]["ansible_python_interpreter"] == "{{ ansible_playbook_python }}"
    local_sync_tasks = local_sync_play["tasks"]

    known_hosts_task = next(item for item in local_sync_tasks if item["name"] == "Ensure VM host keys in local known_hosts")
    known_hosts = known_hosts_task["ansible.builtin.known_hosts"]
    assert known_hosts["path"] == "{{ known_hosts_path }}"
    assert known_hosts["hash_host"] is True


def test_ensure_vm_ssh_access_runs_ansible_playbook(monkeypatch, tmp_path):
    public_key = tmp_path / "id_rsa.pub"
    public_key.write_text("ssh-rsa AAAAB3Nza test@example\n", encoding="utf-8")
    calls: list[tuple[list[str], Path, Optional[str]]] = []

    class Result:
        returncode = 0

    def fake_run_ansible_playbook(command, *, playbook_path, progress_header=None):
        calls.append((list(command), Path(playbook_path), progress_header))
        return Result()

    monkeypatch.setattr(vm_prepare_module, "run_ansible_playbook", fake_run_ansible_playbook)

    vm_prepare_module._ensure_vm_ssh_access("agent", public_key, ["agent", "10.0.0.15", ""])

    assert len(calls) == 1
    command, playbook_path, progress_header = calls[0]
    assert command[:3] == [sys.executable, "-m", "ansible.cli.playbook"]
    assert command[3:5] == ["-i", "localhost,"]
    assert command[-1].endswith("/ansible/vm_ssh.yml")
    assert playbook_path.name == "vm_ssh.yml"
    assert progress_header is None

    payload = json.loads(command[command.index("-e") + 1])
    assert payload["vm_name"] == "agent"
    assert payload["host_public_key"] == "ssh-rsa AAAAB3Nza test@example"
    assert payload["vm_known_hosts"] == ["agent", "10.0.0.15"]
