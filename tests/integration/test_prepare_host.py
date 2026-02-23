import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SSH_DIR = Path.home() / ".config" / "agsekit" / "ssh"


def _clean_env(overrides: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "PROXYCHAINS_CONF_FILE"):
        env.pop(key, None)
    if overrides:
        env.update(overrides)
    return env


def _run(
    command: list[str],
    check: bool = True,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    effective_env = _clean_env(env)
    return subprocess.run(command, check=check, text=True, capture_output=True, cwd=cwd, env=effective_env)

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


def _skip_if_multipass_unusable(result: subprocess.CompletedProcess[str]) -> None:
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    details = "\n".join(part for part in (stderr, stdout) if part)
    markers = (
        "execv failed",
        "snap-confine is packaged without necessary permissions",
    )
    if any(marker in details for marker in markers):
        pytest.skip(f"multipass is installed but not executable in this environment: {details}")


@pytest.mark.host_integration
def test_prepare_installs_multipass_and_generates_keys():
    _require_host_tools()

    snap_bin = Path(_command_path("snap"))
    if snap_bin.exists():
        # The test must be non-destructive for host integration runs.
        _run([str(snap_bin), "--version"], check=False)

    env = _clean_env()
    env["AGSEKIT_LANG"] = "en"
    _run(
        [sys.executable, str(REPO_ROOT / "agsekit"), "prepare", "--non-interactive"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    multipass_bin = Path(_command_path("multipass"))
    assert multipass_bin.exists()
    multipass_check = _run([str(multipass_bin), "--version"], check=False)
    _skip_if_multipass_unusable(multipass_check)
    assert multipass_check.returncode == 0, multipass_check.stderr or multipass_check.stdout

    snap_bin = Path(_command_path("snap"))
    assert snap_bin.exists()
    _run([str(snap_bin), "--version"], check=True)

    private_key = SSH_DIR / "id_rsa"
    public_key = SSH_DIR / "id_rsa.pub"
    assert private_key.exists()
    assert public_key.exists()
