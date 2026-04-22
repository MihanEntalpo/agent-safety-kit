from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import click

from .host_tools import (
    MULTIPASS_WINDOWS_INSTALL_URL,
    msys2_bin_dir,
    windows_multipass_exe_path,
)
from .i18n import tr


WINDOWS_MSYS2_PACKAGES = ["rsync", "openssh"]
WINDOWS_MSYS2_PACKAGE_BINARIES = {
    "rsync": "rsync",
    "openssh": "ssh-keygen",
}


class PrepareBase:
    def __init__(self, *, quiet: bool = False) -> None:
        self.quiet = quiet

    def echo(self, message: str) -> None:
        if not self.quiet:
            click.echo(message)

    def prepare_host(self) -> None:
        self.install_multipass()
        self.ensure_ssh_keygen()
        self.ensure_rsync()

    def install_multipass(self) -> None:
        if shutil.which("multipass") is not None:
            self.echo(tr("prepare.multipass_already_installed"))
            return

        self._install_multipass()

    def ensure_ssh_keygen(self) -> None:
        if shutil.which("ssh-keygen") is not None:
            return

        self._install_ssh_keygen()

        if shutil.which("ssh-keygen") is None:
            raise click.ClickException(tr("prepare.ssh_keygen_missing"))

    def ensure_rsync(self) -> None:
        if shutil.which("rsync") is not None:
            return

        self._install_rsync()

        if shutil.which("rsync") is None:
            raise click.ClickException(tr("prepare.rsync_missing"))

    def _install_multipass(self) -> None:
        raise click.ClickException(tr("prepare.apt_missing"))

    def _install_ssh_keygen(self) -> None:
        raise click.ClickException(tr("prepare.ssh_keygen_missing"))

    def _install_rsync(self) -> None:
        raise click.ClickException(tr("prepare.rsync_missing"))

    @staticmethod
    def is_wsl() -> bool:
        if platform.system() != "Linux":
            return False

        release_paths = [Path("/proc/sys/kernel/osrelease"), Path("/proc/version")]
        for release_path in release_paths:
            try:
                value = release_path.read_text(encoding="utf-8").lower()
            except OSError:
                continue
            if "microsoft" in value or "wsl" in value:
                return True

        release = platform.release().lower()
        return "microsoft" in release or "wsl" in release


class PrepareLinuxDeb(PrepareBase):
    MULTIPASS_PACKAGES = [
        "snapd",
        "qemu-kvm",
        "libvirt-daemon-system",
        "libvirt-clients",
        "bridge-utils",
    ]
    SSH_PACKAGES = ["openssh-client"]
    RSYNC_PACKAGES = ["rsync"]

    def _install_multipass(self) -> None:
        self.echo(tr("prepare.installing_dependencies"))
        self.install_packages_if_missing(self.MULTIPASS_PACKAGES)

        if shutil.which("snap") is None:
            raise click.ClickException(tr("prepare.snap_missing"))

        subprocess.run(["sudo", "snap", "install", "multipass", "--classic"], check=True)
        self.echo(tr("prepare.multipass_installed"))

    def _install_ssh_keygen(self) -> None:
        self.install_packages_if_missing(self.SSH_PACKAGES)

    def _install_rsync(self) -> None:
        self.install_packages_if_missing(self.RSYNC_PACKAGES)

    def install_packages_if_missing(self, packages: list[str]) -> None:
        missing = [package for package in packages if not self.package_installed(package)]
        if not missing:
            self.echo(tr("prepare.host_packages_already_installed"))
            return

        self.echo(tr("prepare.installing_host_packages", packages=", ".join(missing)))

        env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
        subprocess.run(["sudo", "apt-get", "update"], check=True, env=env)
        subprocess.run(["sudo", "apt-get", "install", "-y"] + missing, check=True, env=env)

    @staticmethod
    def package_installed(package: str) -> bool:
        if shutil.which("dpkg-query") is None:
            return False
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", package],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and "install ok installed" in result.stdout


class PrepareLinuxArch(PrepareBase):
    SSH_PACKAGES = ["openssh"]
    RSYNC_PACKAGES = ["rsync"]

    def _install_multipass(self) -> None:
        self.echo(tr("prepare.installing_dependencies"))
        self.echo(tr("prepare.installing_multipass_arch"))

        if shutil.which("yay") is not None:
            aur_helper = "yay"
        elif shutil.which("aura") is not None:
            aur_helper = "aura"
        else:
            raise click.ClickException(tr("prepare.aur_helper_missing"))

        subprocess.run(
            [aur_helper, "-S", "--noconfirm", "multipass", "libvirt", "dnsmasq", "qemu-base"],
            check=True,
        )
        self.echo(tr("prepare.multipass_installed_arch"))

    def _install_ssh_keygen(self) -> None:
        self.install_packages_if_missing(self.SSH_PACKAGES)

    def _install_rsync(self) -> None:
        self.install_packages_if_missing(self.RSYNC_PACKAGES)

    def install_packages_if_missing(self, packages: list[str]) -> None:
        missing = [package for package in packages if not self.package_installed(package)]
        if not missing:
            self.echo(tr("prepare.host_packages_already_installed"))
            return

        self.echo(tr("prepare.installing_host_packages", packages=", ".join(missing)))
        subprocess.run(["sudo", "pacman", "-S", "--needed", "--noconfirm"] + missing, check=True)

    @staticmethod
    def package_installed(package: str) -> bool:
        if shutil.which("pacman") is None:
            return False
        result = subprocess.run(
            ["pacman", "-Q", package],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0


class PrepareMacBrew(PrepareBase):
    LEGACY_MACOS_MULTIPASS_VERSION = "1.14.1"
    LEGACY_MACOS_MAX_MAJOR = 12
    LEGACY_MULTIPASS_CASK = """cask "multipass" do
  version "1.14.1"
  sha256 "f1c6dbd9ded551a00b38a780615f4c96a401c6a9ab8d752e4475007e07e4b0af"

  on_arm do
    postflight do
      File.symlink("/Library/Application Support/com.canonical.multipass/Resources/completions/bash/multipass",
                   "#{HOMEBREW_PREFIX}/etc/bash_completion.d/multipass")
    end
  end

  url "https://github.com/canonical/multipass/releases/download/v#{version}/multipass-#{version}+mac-Darwin.pkg"
  name "Multipass"
  desc "Orchestrates virtual Ubuntu instances"
  homepage "https://github.com/canonical/multipass/"

  livecheck do
    url :url
    strategy :github_latest
  end

  depends_on macos: ">= :mojave"

  pkg "multipass-#{version}+mac-Darwin.pkg"

  uninstall launchctl: "com.canonical.multipassd",
            pkgutil:   "com.canonical.multipass.*",
            delete:    [
              "#{HOMEBREW_PREFIX}/etc/bash_completion.d/multipass",
              "/Applications/Multipass.app",
              "/Library/Application Support/com.canonical.multipass",
              "/Library/Logs/Multipass",
              "/usr/local/bin/multipass",
              "/usr/local/etc/bash_completion.d/multipass",
            ]

  zap trash: [
    "~/Library/Application Support/com.canonical.multipassGui",
    "~/Library/Application Support/multipass",
    "~/Library/Application Support/multipass-gui",
    "~/Library/LaunchAgents/com.canonical.multipass.gui.autostart.plist",
    "~/Library/Preferences/multipass",
    "~/Library/Saved Application State/com.canonical.multipassGui.savedState",
  ]
end
"""

    def _install_multipass(self) -> None:
        self.ensure_brew(tr("prepare.apt_missing"))
        self.echo(tr("prepare.installing_multipass_brew"))
        self.install_multipass_with_brew()
        self.echo(tr("prepare.multipass_installed_brew"))

    def _install_rsync(self) -> None:
        self.ensure_brew(tr("prepare.rsync_missing"))
        self.echo(tr("prepare.installing_rsync_brew"))
        subprocess.run(["brew", "install", "rsync"], check=True)

    @staticmethod
    def ensure_brew(missing_message: str) -> None:
        if shutil.which("brew") is None:
            raise click.ClickException(missing_message)

    def install_multipass_with_brew(self) -> None:
        if not self.is_legacy_macos():
            subprocess.run(["brew", "install", "--cask", "multipass"], check=True)
            return

        with tempfile.TemporaryDirectory(prefix="agsekit-multipass-cask-") as temp_dir:
            cask_path = Path(temp_dir) / "multipass.rb"
            cask_path.write_text(self.LEGACY_MULTIPASS_CASK, encoding="utf-8")
            subprocess.run(["brew", "install", "--cask", str(cask_path)], check=True)

    @classmethod
    def is_legacy_macos(cls) -> bool:
        major_version = cls.macos_major_version()
        return major_version is not None and major_version <= cls.LEGACY_MACOS_MAX_MAJOR

    @staticmethod
    def macos_major_version() -> Optional[int]:
        version = platform.mac_ver()[0]
        if not version:
            return None
        try:
            return int(version.split(".", 1)[0])
        except ValueError:
            return None


class PrepareWin(PrepareBase):
    def prepare_host(self) -> None:
        self.install_multipass()
        self.ensure_msys2_host_packages(WINDOWS_MSYS2_PACKAGES)

    def install_multipass(self) -> None:
        if self.multipass_exists():
            self.echo(tr("prepare.multipass_already_installed"))
            return

        click.echo(tr("prepare.windows_multipass_missing", url=MULTIPASS_WINDOWS_INSTALL_URL))
        if click.confirm(tr("prepare.windows_multipass_download_prompt"), default=True):
            subprocess.run(["cmd", "/c", "start", "", MULTIPASS_WINDOWS_INSTALL_URL], check=False)
        raise click.ClickException(tr("prepare.windows_multipass_required"))

    def ensure_ssh_keygen(self) -> None:
        self.ensure_msys2_host_packages(["openssh"])
        if self.find_tool("ssh-keygen") is None:
            raise click.ClickException(tr("prepare.ssh_keygen_missing"))

    def ensure_rsync(self) -> None:
        self.ensure_msys2_host_packages(["rsync"])
        if self.find_tool("rsync") is None:
            raise click.ClickException(tr("prepare.rsync_missing"))

    def ensure_msys2_host_packages(self, packages: list[str]) -> None:
        missing = self.missing_msys2_packages(packages)
        if not missing:
            self.ensure_msys2_path()
            self.echo(tr("prepare.host_packages_already_installed"))
            return

        prompt = tr("prepare.windows_msys2_install_prompt", packages=", ".join(missing))
        if not click.confirm(prompt, default=True):
            raise click.ClickException(tr("prepare.windows_msys2_install_declined"))

        self.install_msys2_if_missing()
        self.echo(tr("prepare.updating_msys2"))
        self.run_msys2_pacman("pacman -Syu --noconfirm")

        self.echo(tr("prepare.installing_msys2_packages", packages=", ".join(packages)))
        self.run_msys2_pacman("pacman -S --needed --noconfirm " + " ".join(packages))

        self.ensure_msys2_path()

        still_missing = self.missing_msys2_packages(packages)
        if still_missing:
            raise click.ClickException(tr("prepare.windows_msys2_packages_missing", packages=", ".join(still_missing)))

    def missing_msys2_packages(self, packages: list[str]) -> list[str]:
        missing = []
        for package in packages:
            binary = WINDOWS_MSYS2_PACKAGE_BINARIES[package]
            if self.find_tool(binary) is None:
                missing.append(package)
        return missing

    def find_tool(self, binary: str) -> Optional[Path]:
        found = shutil.which(binary)
        if found:
            return Path(found)

        candidate = msys2_bin_dir() / f"{binary}.exe"
        if candidate.exists():
            return candidate
        return None

    def find_msys2_bash(self) -> Optional[Path]:
        candidate = msys2_bin_dir() / "bash.exe"
        if candidate.exists():
            return candidate

        found = shutil.which("bash")
        if found and "msys" in found.lower():
            return Path(found)
        return None

    def ensure_msys2_path(self) -> None:
        msys_bin = msys2_bin_dir()
        if not msys_bin.exists():
            return

        self.echo(tr("prepare.adding_msys2_path", path=str(msys_bin)))
        self.prepend_process_path(msys_bin)
        self.add_user_path(msys_bin)

    def install_msys2_if_missing(self) -> None:
        if self.find_msys2_bash() is not None:
            return

        if shutil.which("winget") is None:
            raise click.ClickException(tr("prepare.winget_missing"))

        self.echo(tr("prepare.installing_msys2"))
        subprocess.run(
            [
                "winget",
                "install",
                "--id",
                "MSYS2.MSYS2",
                "-e",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            check=True,
        )

        if self.find_msys2_bash() is None:
            raise click.ClickException(tr("prepare.msys2_missing_after_install"))

    def run_msys2_pacman(self, command: str) -> None:
        bash = self.find_msys2_bash()
        if bash is None:
            raise click.ClickException(tr("prepare.msys2_bash_missing"))
        subprocess.run([str(bash), "-lc", command], check=True)

    def prepend_process_path(self, entry: Path) -> None:
        path_value = os.environ.get("PATH", "")
        if self.path_contains(path_value, entry):
            return
        os.environ["PATH"] = f"{entry};{path_value}" if path_value else str(entry)

    def add_user_path(self, entry: Path) -> None:
        powershell = shutil.which("powershell") or shutil.which("powershell.exe") or shutil.which("pwsh")
        if powershell is None:
            raise click.ClickException(tr("prepare.powershell_missing"))

        script = (
            "$entry=$env:AGSEKIT_MSYS2_BIN; "
            "$path=[Environment]::GetEnvironmentVariable('Path','User'); "
            "if ([string]::IsNullOrEmpty($path)) { $parts=@() } else { $parts=$path -split ';' }; "
            "foreach ($part in $parts) { if ($part -ieq $entry) { exit 0 } }; "
            "if ([string]::IsNullOrEmpty($path)) { $new=$entry } "
            "else { $new=$path.TrimEnd(';') + ';' + $entry }; "
            "[Environment]::SetEnvironmentVariable('Path',$new,'User')"
        )
        env = {**os.environ, "AGSEKIT_MSYS2_BIN": str(entry)}
        subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=True,
            env=env,
        )

    @staticmethod
    def path_contains(path_value: str, entry: Path) -> bool:
        expected = os.path.normcase(os.path.normpath(str(entry))).lower()
        for item in path_value.split(";"):
            if os.path.normcase(os.path.normpath(item)).lower() == expected:
                return True
        return False

    @staticmethod
    def multipass_exists() -> bool:
        return shutil.which("multipass") is not None or windows_multipass_exe_path().exists()


def choose_prepare(*, quiet: bool = False) -> PrepareBase:
    if PrepareBase.is_wsl():
        raise click.ClickException(tr("prepare.wsl_unsupported"))

    system = platform.system()
    if system == "Windows":
        return PrepareWin(quiet=quiet)
    if system == "Darwin":
        return PrepareMacBrew(quiet=quiet)
    if shutil.which("pacman") is not None:
        return PrepareLinuxArch(quiet=quiet)
    if shutil.which("apt-get") is not None:
        return PrepareLinuxDeb(quiet=quiet)
    return PrepareBase(quiet=quiet)
