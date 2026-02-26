from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pytest


pytestmark = pytest.mark.host_integration

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _require_docker() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker is required for Arch Linux prepare integration test")
    info = _run(["docker", "info"], check=False)
    if info.returncode != 0:
        pytest.skip(info.stderr.strip() or info.stdout.strip() or "docker daemon is unavailable")


def test_prepare_attempt_in_arch_linux_container() -> None:
    _require_docker()

    _run(["docker", "pull", "archlinux:latest"], check=True)

    script = """
set -euo pipefail
pacman -Sy --noconfirm --needed python python-pip git
python -m venv /tmp/agsekit-venv
/tmp/agsekit-venv/bin/pip install -e /workspace
AGSEKIT_LANG=en /tmp/agsekit-venv/bin/agsekit prepare --non-interactive
"""
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{REPO_ROOT}:/workspace",
            "-w",
            "/workspace",
            "archlinux:latest",
            "bash",
            "-lc",
            script,
        ],
        check=False,
    )

    assert result.returncode != 0
    output = f"{result.stdout}\n{result.stderr}"
    assert "No AUR helper found" in output
