from __future__ import annotations

import json

import pytest

from agsekit_cli.vm import to_bytes
from tests.integration.utils import random_vm_name, require_host_tools, run_cli, run_cmd, wait_for, write_config


pytestmark = pytest.mark.host_integration


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    require_host_tools()
    run_cli(["prepare", "--non-interactive"], check=True)


def _state(name: str) -> str:
    payload = json.loads(run_cmd(["multipass", "list", "--format", "json"]).stdout)
    for entry in payload.get("list", []):
        if entry.get("name") == name:
            return str(entry.get("state", "")).lower()
    return "absent"


def _setting(name: str, key: str) -> str:
    return run_cmd(["multipass", "get", f"local.{name}.{key}"]).stdout.strip()


@pytest.fixture
def update_vm_env(tmp_path):
    vm_name = random_vm_name("it-update-vm")
    config_path = tmp_path / "config.yaml"
    payload = {
        "vms": {
            vm_name: {
                # The updated VM uses two of the four available host CPUs.
                "cpu": 2,
                "ram": "2G",
                "disk": "5G",
            }
        },
        "agents": {
            "test-sleeper": {
                "type": "custom",
                "command": "sleep",
                "vm": vm_name,
            }
        },
    }
    write_config(config_path, payload)
    launch_result = run_cmd(
        [
            "multipass",
            "launch",
            "24.04",
            "--name",
            vm_name,
            "--cpus",
            "2",
            "--memory",
            "1G",
            "--disk",
            "5G",
            "--timeout",
            "120",
        ],
        check=False,
    )
    wait_for(
        lambda: _state(vm_name) == "running",
        timeout=180.0,
        message="test VM did not become running",
    )
    if launch_result.returncode != 0 and _state(vm_name) != "running":
        pytest.fail(launch_result.stderr or launch_result.stdout or "Multipass launch failed")
    try:
        yield vm_name, config_path
    finally:
        run_cmd(["multipass", "delete", vm_name], check=False)
        run_cmd(["multipass", "purge"], check=False)


def test_update_vm_changes_stopped_vm_without_starting_it(update_vm_env) -> None:
    vm_name, config_path = update_vm_env
    run_cmd(["multipass", "stop", vm_name], check=True)
    wait_for(lambda: _state(vm_name) == "stopped", timeout=120.0, message="VM did not stop")

    result = run_cli(["update-vm", vm_name, "--config", str(config_path), "--non-interactive"], check=True)

    assert "Updated VM" in result.stdout
    assert _state(vm_name) == "stopped"
    assert _setting(vm_name, "cpus") == "2"
    assert to_bytes(_setting(vm_name, "memory")) == 2 * (1024 ** 3)


def test_update_vm_reports_running_agent_before_forced_restart(update_vm_env) -> None:
    vm_name, config_path = update_vm_env
    pid = run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            "nohup sleep 120 >/tmp/agsekit-update-test.log 2>&1 & echo $!",
        ],
        check=True,
    ).stdout.strip()
    try:
        result = run_cli(
            ["update-vm", vm_name, "--force", "--config", str(config_path), "--non-interactive"],
            check=True,
        )

        assert "Configured agents are still running" in result.stdout
        assert "test-sleeper" in result.stdout
        assert _state(vm_name) == "running"
        assert _setting(vm_name, "cpus") == "2"
        assert to_bytes(_setting(vm_name, "memory")) == 2 * (1024 ** 3)
    finally:
        if pid:
            run_cmd(["multipass", "exec", vm_name, "--", "kill", pid], check=False)


def test_update_vm_skips_suspended_vm(update_vm_env) -> None:
    vm_name, config_path = update_vm_env
    run_cmd(["multipass", "suspend", vm_name], check=True)
    wait_for(lambda: _state(vm_name) == "suspended", timeout=120.0, message="VM did not suspend")

    result = run_cli(["update-vm", vm_name, "--config", str(config_path), "--non-interactive"], check=True)

    assert "is suspended and cannot be updated" in result.stdout
    assert _state(vm_name) == "suspended"
    assert _setting(vm_name, "cpus") == "2"
    assert to_bytes(_setting(vm_name, "memory")) == 1024 ** 3
