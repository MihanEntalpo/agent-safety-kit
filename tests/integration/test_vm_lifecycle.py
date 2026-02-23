from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

import pytest
import yaml

from agsekit_cli.vm import create_all_vms_from_config, create_vm_from_config


pytestmark = pytest.mark.host_integration

REPO_ROOT = Path(__file__).resolve().parents[2]


def _clean_env(overrides: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "PROXYCHAINS_CONF_FILE"):
        env.pop(key, None)
    if overrides:
        env.update(overrides)
    return env


def _sudo_prefix() -> list[str]:
    return [] if os.geteuid() == 0 else ["sudo", "-n"]


def _run(
    command: list[str],
    check: bool = True,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    effective_env = _clean_env(env)
    return subprocess.run(command, check=check, text=True, capture_output=True, cwd=cwd, env=effective_env)


def _run_cli(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    env = _clean_env()
    env["AGSEKIT_LANG"] = "en"
    return _run([sys.executable, str(REPO_ROOT / "agsekit"), *args], check=check, cwd=REPO_ROOT, env=env)


def _run_sudo(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(_sudo_prefix() + command, check=check)


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


def _random_vm_name(prefix: str = "it-vm") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _write_vm_config(config_path: Path, vm_map: dict[str, dict[str, object]]) -> None:
    config_path.write_text(yaml.safe_dump({"vms": vm_map}, sort_keys=False), encoding="utf-8")


def _instance_state(name: str) -> Optional[str]:
    result = _run(["multipass", "list", "--format", "json"], check=True)
    payload = json.loads(result.stdout)
    for entry in payload.get("list", []):
        if entry.get("name") == name:
            state = entry.get("state")
            return str(state).lower() if state else None
    return None


def _instance_exists(name: str) -> bool:
    return _instance_state(name) is not None


def _delete_if_exists(names: list[str]) -> None:
    for name in names:
        if not _instance_exists(name):
            continue
        _run(["multipass", "delete", name], check=False)
    _run(["multipass", "purge"], check=False)


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


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    _require_host_tools()
    if shutil.which("multipass") is None:
        _run_cli(["prepare", "--non-interactive"], check=True)
    check = _run(["multipass", "version"], check=False)
    _skip_if_multipass_unusable(check)
    if check.returncode != 0:
        pytest.skip(check.stderr or check.stdout or "multipass is not ready")


@pytest.fixture
def managed_vms():
    names: list[str] = []
    try:
        yield names
    finally:
        _delete_if_exists(names)


def test_create_vm_from_config_creates_vm(managed_vms, tmp_path):
    vm_name = _random_vm_name()
    managed_vms.append(vm_name)
    config_path = tmp_path / "config.yaml"
    _write_vm_config(
        config_path,
        {
            vm_name: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            }
        },
    )

    _message, mismatch = create_vm_from_config(str(config_path), vm_name)

    assert mismatch is None
    assert _instance_state(vm_name) == "running"


def test_create_vm_from_config_is_idempotent(managed_vms, tmp_path):
    vm_name = _random_vm_name()
    managed_vms.append(vm_name)
    config_path = tmp_path / "config.yaml"
    _write_vm_config(
        config_path,
        {
            vm_name: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            }
        },
    )

    first_message, first_mismatch = create_vm_from_config(str(config_path), vm_name)
    second_message, second_mismatch = create_vm_from_config(str(config_path), vm_name)

    assert first_mismatch is None
    assert second_mismatch is None
    assert first_message
    assert second_message
    assert _instance_state(vm_name) == "running"


def test_create_vm_from_config_reports_resource_mismatch(managed_vms, tmp_path):
    vm_name = _random_vm_name()
    managed_vms.append(vm_name)
    config_path = tmp_path / "config.yaml"
    _write_vm_config(
        config_path,
        {
            vm_name: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            }
        },
    )
    _message, mismatch = create_vm_from_config(str(config_path), vm_name)
    assert mismatch is None

    _write_vm_config(
        config_path,
        {
            vm_name: {
                "cpu": 2,
                "ram": "1G",
                "disk": "5G",
            }
        },
    )
    continue_message, mismatch_message = create_vm_from_config(str(config_path), vm_name)

    assert continue_message
    assert mismatch_message
    assert _instance_state(vm_name) == "running"


def test_create_all_vms_from_config_creates_multiple_vms(managed_vms, tmp_path):
    vm_one = _random_vm_name()
    vm_two = _random_vm_name()
    managed_vms.extend([vm_one, vm_two])
    config_path = tmp_path / "config.yaml"
    _write_vm_config(
        config_path,
        {
            vm_one: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            },
            vm_two: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            },
        },
    )

    messages, mismatches = create_all_vms_from_config(str(config_path))

    assert len(messages) >= 2
    assert not mismatches
    assert _instance_state(vm_one) == "running"
    assert _instance_state(vm_two) == "running"


def test_start_and_stop_vm_commands_change_state(managed_vms, tmp_path):
    vm_name = _random_vm_name()
    managed_vms.append(vm_name)
    config_path = tmp_path / "config.yaml"
    _write_vm_config(
        config_path,
        {
            vm_name: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            }
        },
    )
    _message, mismatch = create_vm_from_config(str(config_path), vm_name)
    assert mismatch is None

    stop_result = _run_cli(["stop-vm", vm_name, "--config", str(config_path), "--non-interactive"], check=True)
    assert stop_result.returncode == 0
    assert _instance_state(vm_name) in {"stopped", "suspended"}

    start_result = _run_cli(["start-vm", vm_name, "--config", str(config_path), "--non-interactive"], check=True)
    assert start_result.returncode == 0
    assert _instance_state(vm_name) == "running"


def test_destroy_vm_command_deletes_single_instance(managed_vms, tmp_path):
    vm_one = _random_vm_name()
    vm_two = _random_vm_name()
    managed_vms.extend([vm_one, vm_two])
    config_path = tmp_path / "config.yaml"
    _write_vm_config(
        config_path,
        {
            vm_one: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            },
            vm_two: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            },
        },
    )
    messages, mismatches = create_all_vms_from_config(str(config_path))
    assert messages
    assert not mismatches

    destroy_result = _run_cli(
        ["destroy-vm", vm_one, "--config", str(config_path), "-y", "--non-interactive"],
        check=True,
    )
    assert destroy_result.returncode == 0
    assert not _instance_exists(vm_one)
    assert _instance_exists(vm_two)


def test_destroy_vm_all_deletes_all_instances(managed_vms, tmp_path):
    vm_one = _random_vm_name()
    vm_two = _random_vm_name()
    managed_vms.extend([vm_one, vm_two])
    config_path = tmp_path / "config.yaml"
    _write_vm_config(
        config_path,
        {
            vm_one: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            },
            vm_two: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            },
        },
    )
    messages, mismatches = create_all_vms_from_config(str(config_path))
    assert messages
    assert not mismatches

    destroy_all_result = _run_cli(
        ["destroy-vm", "--all", "--config", str(config_path), "-y", "--non-interactive"],
        check=True,
    )
    assert destroy_all_result.returncode == 0
    assert not _instance_exists(vm_one)
    assert not _instance_exists(vm_two)
