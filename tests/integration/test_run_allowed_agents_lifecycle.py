from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import pytest
import yaml


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


def _run_cli(args: list[str], check: bool = True, cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
    env = _clean_env({"AGSEKIT_LANG": "en"})
    return _run([sys.executable, str(REPO_ROOT / "agsekit"), *args], check=check, cwd=cwd or REPO_ROOT, env=env)


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


def _random_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _instance_exists(name: str) -> bool:
    result = _run(["multipass", "list", "--format", "json"], check=True)
    payload = json.loads(result.stdout)
    for entry in payload.get("list", []):
        if entry.get("name") == name:
            return True
    return False


def _list_instances() -> list[str]:
    result = _run(["multipass", "list", "--format", "json"], check=True)
    payload = json.loads(result.stdout)
    return [str(entry.get("name")) for entry in payload.get("list", []) if entry.get("name")]


def _ensure_vm_started(name: str) -> None:
    _run(["multipass", "start", name], check=False)


def _delete_if_exists(name: str) -> None:
    if not _instance_exists(name):
        return
    _run(["multipass", "delete", name], check=False)
    _run(["multipass", "purge"], check=False)


def _launch_vm(name: str) -> None:
    launch_cmd = ["multipass", "launch", "--name", name, "--cpus", "1", "--memory", "1G", "--disk", "5G"]
    for attempt in range(1, 4):
        result = _run(launch_cmd, check=False)
        if result.returncode == 0:
            return
        stderr = (result.stderr or "").lower()
        if attempt < 3 and "remote" in stderr and "unknown or unreachable" in stderr:
            _run(["multipass", "find"], check=False)
            time.sleep(attempt)
            continue
        if "available disk" in stderr and "below minimum for this image" in stderr:
            pytest.skip(result.stderr.strip() or "Not enough free disk for multipass launch")
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "multipass launch failed")


def _install_dummy_qwen(vm_name: str) -> None:
    script = """#!/usr/bin/env bash
set -euo pipefail
echo dummy-qwen-ok >/dev/null
"""
    _run(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            f"cat > /tmp/it-qwen.sh <<'EOF'\n{script}\nEOF\nsudo mv /tmp/it-qwen.sh /usr/local/bin/qwen && sudo chmod +x /usr/local/bin/qwen",
        ],
        check=True,
    )


def _write_config(config_path: Path, vm_name: str, source: Path, target: Path) -> None:
    payload = {
        "vms": {
            vm_name: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            }
        },
        "mounts": [
            {
                "source": str(source),
                "target": str(target),
                "vm": vm_name,
                "allowed_agents": ["allowed-agent"],
            }
        ],
        "agents": {
            "allowed-agent": {
                "type": "qwen",
                "vm": vm_name,
            },
            "blocked-agent": {
                "type": "qwen",
                "vm": vm_name,
            },
        },
    }
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    _require_host_tools()
    if shutil.which("multipass") is None:
        _run_cli(["prepare", "--non-interactive"], check=True)
    check = _run(["multipass", "version"], check=False)
    _skip_if_multipass_unusable(check)
    if check.returncode != 0:
        pytest.skip(check.stderr or check.stdout or "multipass is not ready")


@pytest.fixture(scope="module")
def run_test_vm() -> str:
    existing_instances = _list_instances()
    if existing_instances:
        vm_name = existing_instances[0]
        _ensure_vm_started(vm_name)
        yield vm_name
        return

    vm_name = _random_name("it-run-allow-vm")
    _delete_if_exists(vm_name)
    _launch_vm(vm_name)
    try:
        yield vm_name
    finally:
        _delete_if_exists(vm_name)


@pytest.fixture(scope="module")
def host_mount_root() -> Path:
    root = Path.home() / ".agsekit-it-run-allowed" / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_run_respects_mount_allowed_agents(run_test_vm: str, host_mount_root: Path, tmp_path: Path) -> None:
    source = host_mount_root / "source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    target = Path("/home/ubuntu") / _random_name("it-target-allow")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, run_test_vm, source, target)

    _install_dummy_qwen(run_test_vm)

    try:
        mount_result = _run_cli(
            ["mount", str(source), "--config", str(config_path), "--non-interactive", "--debug"],
            check=True,
        )
        assert mount_result.returncode == 0

        denied = _run_cli(
            [
                "run",
                "blocked-agent",
                str(source),
                "--config",
                str(config_path),
                "--disable-backups",
                "--non-interactive",
                "--debug",
            ],
            check=False,
        )
        assert denied.returncode != 0
        denied_output = f"{denied.stdout}\n{denied.stderr}"
        assert "allowed_agents" in denied_output
        assert "blocked-agent" in denied_output

        allowed = _run_cli(
            [
                "run",
                "allowed-agent",
                str(nested),
                "--config",
                str(config_path),
                "--disable-backups",
                "--non-interactive",
                "--debug",
            ],
            check=False,
        )
        assert allowed.returncode == 0, f"stdout={allowed.stdout}\nstderr={allowed.stderr}"
    finally:
        _run_cli(
            ["umount", str(source), "--config", str(config_path), "--non-interactive", "--debug"],
            check=False,
        )
