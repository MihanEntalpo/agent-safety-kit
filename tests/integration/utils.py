import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
INJECTED_ENV_VARS = (
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "DYLD_INSERT_LIBRARIES",
    "PROXYCHAINS_CONF_FILE",
    "PROXYCHAINS_QUIET_MODE",
)


def clean_env(overrides: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in INJECTED_ENV_VARS:
        env.pop(key, None)
    if overrides:
        env.update(overrides)
    return env


def run_cmd(
    command: list[str],
    *,
    check: bool = True,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        text=True,
        capture_output=capture_output,
        cwd=cwd,
        env=env,
    )


def run_cli(
    args: list[str],
    *,
    check: bool = True,
    cwd: Optional[Path] = None,
    env_overrides: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    env = clean_env({"AGSEKIT_LANG": "en", **(env_overrides or {})})
    command = [sys.executable, str(REPO_ROOT / "agsekit"), *args]
    return run_cmd(command, check=check, cwd=cwd or REPO_ROOT, env=env)


def start_cli(
    args: list[str],
    *,
    cwd: Optional[Path] = None,
    env_overrides: Optional[dict[str, str]] = None,
) -> subprocess.Popen[str]:
    env = clean_env({"AGSEKIT_LANG": "en", **(env_overrides or {})})
    command = [sys.executable, str(REPO_ROOT / "agsekit"), *args]
    return subprocess.Popen(
        command,
        cwd=cwd or REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_for(
    predicate: Callable[[], bool],
    timeout: float,
    message: str,
    interval: float = 0.2,
) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError(message)


def write_config(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def random_vm_name(prefix: str = "it-vm") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def require_host_tools() -> None:
    if shutil.which("apt-get") is None and shutil.which("pacman") is None:
        pytest.skip("apt-get or pacman is required for host integration tests")
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


def skip_if_systemd_user_unavailable() -> None:
    result = run_cmd(
        ["systemctl", "--user", "show-environment"],
        check=False,
        env=clean_env(),
    )
    if result.returncode != 0:
        pytest.skip("systemd --user is not available in this environment")
