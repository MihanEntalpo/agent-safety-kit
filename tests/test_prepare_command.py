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
import agsekit_cli.prepare_strategies as prepare_strategies
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

    class FakePrepare:
        def prepare_host(self):
            calls.extend(["install", "ssh-keygen", "rsync"])

    monkeypatch.setattr(prepare_module, "choose_prepare", lambda **_kwargs: FakePrepare())
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
        prepare_strategies.shutil,
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

    class FakePrepare:
        def __init__(self, quiet: bool):
            self.quiet = quiet

        def prepare_host(self):
            calls.append(self.quiet)

    monkeypatch.setattr(prepare_module, "choose_prepare", lambda **kwargs: FakePrepare(kwargs["quiet"]))

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

    class FakePrepare:
        def __init__(self, quiet: bool):
            self.quiet = quiet

        def prepare_host(self):
            calls.extend([f"install:{self.quiet}", f"ssh-keygen:{self.quiet}", f"rsync:{self.quiet}"])

    monkeypatch.setattr(prepare_module, "choose_prepare", lambda **kwargs: FakePrepare(kwargs["quiet"]))
    monkeypatch.setattr(prepare_module, "ensure_host_ssh_keypair", lambda *args, **kwargs: None)

    prepare_module.run_prepare(debug=False, progress=DummyProgress())

    assert calls == ["suspend", "enter", "install:True", "ssh-keygen:True", "rsync:True", "exit"]


def test_choose_prepare_prefers_arch_over_debian(monkeypatch):
    def fake_which(binary: str):
        if binary == "pacman":
            return "/usr/bin/pacman"
        if binary == "apt-get":
            return "/usr/bin/apt-get"
        return None

    monkeypatch.setattr(prepare_strategies.shutil, "which", fake_which)

    assert isinstance(prepare_module.choose_prepare(), prepare_strategies.PrepareLinuxArch)


def test_choose_prepare_uses_debian_when_pacman_absent(monkeypatch):
    def fake_which(binary: str):
        if binary == "pacman":
            return None
        if binary == "apt-get":
            return "/usr/bin/apt-get"
        return None

    monkeypatch.setattr(prepare_strategies.shutil, "which", fake_which)

    assert isinstance(prepare_module.choose_prepare(), prepare_strategies.PrepareLinuxDeb)


def test_install_multipass_does_not_try_to_install_inside_wsl(monkeypatch):
    monkeypatch.setattr(prepare_strategies.shutil, "which", lambda _binary: None)
    monkeypatch.setattr(prepare_strategies.PrepareBase, "is_wsl", staticmethod(lambda: True))

    with pytest.raises(prepare_module.click.ClickException) as exc_info:
        prepare_module.choose_prepare()

    assert "WSL is not supported" in str(exc_info.value)


def test_install_multipass_is_unsupported_in_wsl_even_when_multipass_exists(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(prepare_strategies.shutil, "which", lambda binary: "/usr/local/bin/multipass" if binary == "multipass" else None)
    monkeypatch.setattr(prepare_strategies.PrepareBase, "is_wsl", staticmethod(lambda: True))
    monkeypatch.setattr(prepare_strategies.PrepareLinuxDeb, "_install_multipass", lambda _self: calls.append("debian"))

    with pytest.raises(prepare_module.click.ClickException) as exc_info:
        prepare_module.choose_prepare()

    assert calls == []
    assert "WSL is not supported" in str(exc_info.value)


def test_choose_prepare_uses_homebrew_on_macos(monkeypatch):
    def fake_which(binary: str):
        del binary
        return None

    monkeypatch.setattr(prepare_strategies.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(prepare_strategies.shutil, "which", fake_which)

    assert isinstance(prepare_module.choose_prepare(), prepare_strategies.PrepareMacBrew)


def test_install_multipass_arch_requires_aur_helper(monkeypatch):
    monkeypatch.setattr(prepare_strategies.shutil, "which", lambda _binary: None)

    with pytest.raises(prepare_module.click.ClickException) as exc_info:
        prepare_strategies.PrepareLinuxArch()._install_multipass()

    assert "AUR helper" in str(exc_info.value)


def test_install_multipass_brew_uses_current_cask_on_macos_13_or_newer(monkeypatch):
    commands: list[list[str]] = []

    def fake_run(command, check):
        commands.append(command)
        assert check is True

    monkeypatch.setattr(prepare_strategies.subprocess, "run", fake_run)
    monkeypatch.setattr(prepare_strategies.shutil, "which", lambda binary: "/opt/homebrew/bin/brew" if binary == "brew" else None)
    monkeypatch.setattr(prepare_strategies.platform, "mac_ver", lambda: ("13.6.1", ("", "", ""), "arm64"))

    prepare_strategies.PrepareMacBrew()._install_multipass()

    assert commands == [["brew", "install", "--cask", "multipass"]]


def test_install_multipass_brew_uses_legacy_cask_on_old_macos(monkeypatch):
    commands: list[list[str]] = []
    captured_cask = ""

    def fake_run(command, check):
        nonlocal captured_cask
        commands.append(command)
        assert check is True
        cask_path = Path(command[-1])
        assert cask_path.exists()
        captured_cask = cask_path.read_text(encoding="utf-8")

    monkeypatch.setattr(prepare_strategies.subprocess, "run", fake_run)
    monkeypatch.setattr(prepare_strategies.shutil, "which", lambda binary: "/opt/homebrew/bin/brew" if binary == "brew" else None)
    monkeypatch.setattr(prepare_strategies.platform, "mac_ver", lambda: ("12.7.6", ("", "", ""), "x86_64"))

    prepare_strategies.PrepareMacBrew()._install_multipass()

    assert len(commands) == 1
    assert commands[0][:3] == ["brew", "install", "--cask"]
    assert commands[0][3].endswith("/multipass.rb")
    assert 'version "1.14.1"' in captured_cask
    assert "multipass-#{version}+mac-Darwin.pkg" in captured_cask


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

    monkeypatch.setattr(prepare_strategies.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(prepare_strategies.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_strategies.subprocess, "run", fake_run)

    prepare_module.choose_prepare().ensure_rsync()

    assert commands == [["brew", "install", "rsync"]]


def test_ensure_rsync_skips_homebrew_when_available_on_macos(monkeypatch):
    commands: list[list[str]] = []

    def fake_which(binary: str):
        if binary == "rsync":
            return "/usr/bin/rsync"
        if binary == "brew":
            return "/opt/homebrew/bin/brew"
        return None

    monkeypatch.setattr(prepare_strategies.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(prepare_strategies.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_strategies.subprocess, "run", lambda command, check: commands.append(command))

    prepare_module.choose_prepare().ensure_rsync()

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

    def fake_install(_self, packages):
        nonlocal installed
        calls.append(packages)
        installed = True

    monkeypatch.setattr(prepare_strategies.platform, "system", lambda: "Linux")
    monkeypatch.setattr(prepare_strategies.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_strategies.PrepareBase, "is_wsl", staticmethod(lambda: False))
    monkeypatch.setattr(prepare_strategies.PrepareLinuxDeb, "install_packages_if_missing", fake_install)

    prepare_module.choose_prepare().ensure_rsync()

    assert calls == [["rsync"]]


def test_windows_msys2_host_packages_install_missing_tools(monkeypatch, tmp_path):
    msys_root = tmp_path / "msys64"
    msys_bin = msys_root / "usr" / "bin"
    commands: list[list[str]] = []
    prompts: list[str] = []

    monkeypatch.setenv("AGSEKIT_MSYS2_ROOT", str(msys_root))
    monkeypatch.setenv("PATH", "")

    def fake_which(binary: str):
        if binary == "winget":
            return "C:/Windows/System32/winget.exe"
        if binary == "powershell":
            return "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
        return None

    def fake_confirm(prompt: str, default: bool):
        prompts.append(prompt)
        assert default is True
        return True

    def fake_run(command, check, env=None):
        del env
        commands.append([str(part) for part in command])
        assert check is True
        if command[0] == "winget":
            msys_bin.mkdir(parents=True)
            (msys_bin / "bash.exe").write_text("", encoding="utf-8")
        elif len(command) >= 3 and command[2].startswith("pacman -S --needed"):
            (msys_bin / "rsync.exe").write_text("", encoding="utf-8")
            (msys_bin / "ssh-keygen.exe").write_text("", encoding="utf-8")

    monkeypatch.setattr(prepare_strategies.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_strategies.click, "confirm", fake_confirm)
    monkeypatch.setattr(prepare_strategies.subprocess, "run", fake_run)

    prepare_strategies.PrepareWin().ensure_msys2_host_packages(prepare_strategies.WINDOWS_MSYS2_PACKAGES)

    assert "rsync" in prompts[0]
    assert "openssh" in prompts[0]
    assert commands == [
        [
            "winget",
            "install",
            "--id",
            "MSYS2.MSYS2",
            "-e",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        [str(msys_bin / "bash.exe"), "-lc", "pacman -Syu --noconfirm"],
        [str(msys_bin / "bash.exe"), "-lc", "pacman -S --needed --noconfirm rsync openssh"],
        [
            "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            commands[-1][5],
        ],
    ]
    assert str(msys_bin) in prepare_strategies.os.environ["PATH"]


def test_windows_msys2_host_packages_decline_aborts(monkeypatch, tmp_path):
    monkeypatch.setenv("AGSEKIT_MSYS2_ROOT", str(tmp_path / "msys64"))
    monkeypatch.setattr(prepare_strategies.shutil, "which", lambda _binary: None)
    monkeypatch.setattr(prepare_strategies.click, "confirm", lambda _prompt, default: False)
    monkeypatch.setattr(
        prepare_strategies.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("installer commands must not run"),
    )

    with pytest.raises(prepare_module.click.ClickException) as exc_info:
        prepare_strategies.PrepareWin().ensure_msys2_host_packages(["rsync"])

    assert "not installed" in str(exc_info.value)


def test_prepare_host_dependencies_checks_windows_multipass_before_msys2(monkeypatch):
    calls: list[str] = []

    class FakePrepare:
        def __init__(self, quiet: bool):
            self.quiet = quiet

        def prepare_host(self):
            calls.extend([f"multipass:{self.quiet}", f"msys2:rsync,openssh:{self.quiet}"])

    monkeypatch.setattr(prepare_module, "choose_prepare", lambda **kwargs: FakePrepare(kwargs["quiet"]))

    prepare_module._prepare_host_dependencies(quiet=True)

    assert calls == ["multipass:True", "msys2:rsync,openssh:True"]


def test_install_multipass_on_native_windows_requires_manual_multipass(monkeypatch):
    def fake_which(binary: str):
        if binary == "multipass":
            return None
        return None

    monkeypatch.setattr(prepare_strategies.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_strategies.click, "confirm", lambda _prompt, default: False)

    with pytest.raises(prepare_module.click.ClickException) as exc_info:
        prepare_strategies.PrepareWin().install_multipass()

    assert "Install Multipass for Windows" in str(exc_info.value)


def test_install_multipass_on_native_windows_accepts_standard_install_path(monkeypatch, tmp_path):
    multipass_exe = tmp_path / "Multipass" / "bin" / "multipass.exe"
    multipass_exe.parent.mkdir(parents=True)
    multipass_exe.write_text("", encoding="utf-8")

    monkeypatch.setenv("AGSEKIT_MULTIPASS_EXE", str(multipass_exe))
    monkeypatch.setattr(prepare_strategies.shutil, "which", lambda _binary: None)
    monkeypatch.setattr(
        prepare_strategies.click,
        "confirm",
        lambda *_args, **_kwargs: pytest.fail("download prompt must not be shown"),
    )

    prepare_strategies.PrepareWin().install_multipass()


def test_install_multipass_debian_installs_only_missing_host_packages(monkeypatch):
    commands: list[list[str]] = []

    monkeypatch.setattr(prepare_strategies.PrepareLinuxDeb, "package_installed", staticmethod(lambda package: package != "snapd"))
    monkeypatch.setattr(prepare_strategies.shutil, "which", lambda binary: "/usr/bin/snap" if binary == "snap" else None)

    def fake_run(command, check, env=None):
        del env
        commands.append(command)
        assert check is True

    monkeypatch.setattr(prepare_strategies.subprocess, "run", fake_run)

    prepare_strategies.PrepareLinuxDeb()._install_multipass()

    assert commands == [
        ["sudo", "apt-get", "update"],
        ["sudo", "apt-get", "install", "-y", "snapd"],
        ["sudo", "snap", "install", "multipass", "--classic"],
    ]


def test_install_multipass_debian_skips_package_install_when_packages_exist(monkeypatch):
    commands: list[list[str]] = []

    monkeypatch.setattr(prepare_strategies.PrepareLinuxDeb, "package_installed", staticmethod(lambda _package: True))
    monkeypatch.setattr(prepare_strategies.shutil, "which", lambda binary: "/usr/bin/snap" if binary == "snap" else None)

    def fake_run(command, check, env=None):
        del env
        commands.append(command)
        assert check is True

    monkeypatch.setattr(prepare_strategies.subprocess, "run", fake_run)

    prepare_strategies.PrepareLinuxDeb()._install_multipass()

    assert commands == [["sudo", "snap", "install", "multipass", "--classic"]]


def test_package_data_includes_http_proxy_runner_script():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["agsekit_cli"]

    assert "run_with_http_proxy.sh" in package_data
    assert "run_agent.sh" in package_data


def test_manifest_includes_http_proxy_runner_script():
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")

    assert "include agsekit_cli/run_with_http_proxy.sh" in manifest
    assert "include agsekit_cli/run_agent.sh" in manifest


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

    monkeypatch.setattr(prepare_strategies.shutil, "which", fake_which)
    monkeypatch.setattr(prepare_strategies.subprocess, "run", fake_run)

    prepare_strategies.PrepareLinuxArch()._install_multipass()

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

    run_agent_task = next(item for item in tasks if item["name"] == "Install agsekit run wrapper script")
    run_agent_copy = run_agent_task["ansible.builtin.copy"]
    assert run_agent_copy["src"] == "{{ playbook_dir }}/../run_agent.sh"
    assert run_agent_copy["dest"] == "/usr/bin/agsekit-run_agent.sh"
    assert run_agent_copy["mode"] == "0755"


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


def test_vm_ssh_ansible_vars_use_builtin_ssh_and_configured_key(tmp_path):
    private_key = tmp_path / "custom-ssh" / "id_rsa"
    private_key.parent.mkdir()
    private_key.write_text("private", encoding="utf-8")

    payload = vm_prepare_module.vm_ssh_ansible_vars("agent", "10.0.0.15", private_key)

    assert payload["vm_name"] == "agent"
    assert payload["ansible_host"] == "10.0.0.15"
    assert payload["ansible_connection"] == "ssh"
    assert payload["ansible_user"] == "ubuntu"
    assert payload["ansible_ssh_private_key_file"] == str(private_key.resolve())
    assert "StrictHostKeyChecking=yes" in payload["ansible_ssh_common_args"]
    assert "ConnectTimeout=10" in payload["ansible_ssh_common_args"]


def test_ensure_vm_packages_runs_over_builtin_ssh(monkeypatch, tmp_path):
    private_key = tmp_path / "custom-ssh" / "id_rsa"
    private_key.parent.mkdir()
    private_key.write_text("private", encoding="utf-8")
    calls: list[tuple[list[str], Path]] = []

    class Result:
        returncode = 0

    def fake_run_ansible_playbook(command, *, playbook_path, **_kwargs):
        calls.append((list(command), Path(playbook_path)))
        return Result()

    monkeypatch.setattr(vm_prepare_module, "run_ansible_playbook", fake_run_ansible_playbook)

    vm_prepare_module._ensure_vm_packages("agent", "10.0.0.15", private_key)

    assert len(calls) == 1
    command, playbook_path = calls[0]
    assert playbook_path.name == "vm_packages.yml"
    payload = json.loads(command[command.index("-e") + 1])
    assert payload["vm_name"] == "agent"
    assert payload["ansible_host"] == "10.0.0.15"
    assert payload["ansible_connection"] == "ssh"
    assert payload["ansible_ssh_private_key_file"] == str(private_key.resolve())
