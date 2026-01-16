import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SSH_DIR = Path.home() / ".config" / "agsekit" / "ssh"


def _sudo_prefix() -> list[str]:
    return [] if os.geteuid() == 0 else ["sudo", "-n"]


def _run(
    command: list[str],
    check: bool = True,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, text=True, capture_output=True, cwd=cwd, env=env)


def _run_sudo(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(_sudo_prefix() + command, check=check)


def _dpkg_installed(package: str) -> bool:
    result = subprocess.run(
        ["dpkg", "-s", package],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.returncode == 0


def _require_host_tools() -> None:
    if shutil.which("apt-get") is None:
        pytest.skip("apt-get is required for host integration tests")
    if os.geteuid() != 0 and shutil.which("sudo") is None:
        pytest.skip("sudo or root access is required for host integration tests")
    if os.geteuid() != 0:
        sudo_check = subprocess.run(
            ["sudo", "-n", "true"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if sudo_check.returncode != 0:
            pytest.skip("passwordless sudo is required for host integration tests")


def _command_path(name: str) -> str:
    return shutil.which(name) or f"/snap/bin/{name}"


@pytest.mark.host_integration
def test_prepare_installs_multipass_and_generates_keys():
    _require_host_tools()

    if _dpkg_installed("snapd"):
        _run_sudo(["apt-get", "remove", "-y", "snapd"])

    assert not _dpkg_installed("snapd")

    snap_bin = Path(_command_path("snap"))
    if snap_bin.exists():
        snap_pre = subprocess.run([str(snap_bin), "--version"], check=False, text=True, capture_output=True)
        assert snap_pre.returncode != 0

    env = os.environ.copy()
    env["AGSEKIT_LANG"] = "en"
    _run(
        [sys.executable, str(REPO_ROOT / "agsekit"), "prepare", "--non-interactive"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    multipass_bin = Path(_command_path("multipass"))
    assert multipass_bin.exists()
    _run([str(multipass_bin), "--version"], check=True)

    snap_bin = Path(_command_path("snap"))
    assert snap_bin.exists()
    _run([str(snap_bin), "--version"], check=True)

    private_key = SSH_DIR / "id_rsa"
    public_key = SSH_DIR / "id_rsa.pub"
    assert private_key.exists()
    assert public_key.exists()
