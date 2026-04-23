from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.test_systemd_portforward_lifecycle import (
    _expected_agsekit_bin,
    _systemd_invocation_id,
    _systemd_is_active,
)
from tests.integration.utils import REPO_ROOT, random_vm_name, require_host_tools, run_cli, run_cmd, wait_for, write_config


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    require_host_tools()
    run_cli(["prepare", "--non-interactive"], check=True)


@pytest.fixture(scope="module")
def portforward_config(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("daemon-portforward")
    vm_name = random_vm_name("it-daemon-port")
    config_path = tmp_path / "config.yaml"
    payload = {
        "vms": {
            vm_name: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
                "port-forwarding": [],
            }
        }
    }
    write_config(config_path, payload)
    try:
        run_cli(["create-vm", vm_name, "--config", str(config_path), "--non-interactive"], check=True)
    except Exception:
        run_cmd(["multipass", "delete", vm_name], check=False)
        run_cmd(["multipass", "purge"], check=False)
        raise
    try:
        yield config_path, vm_name, None, None, None
    finally:
        run_cmd(["multipass", "delete", vm_name], check=False)
        run_cmd(["multipass", "purge"], check=False)


pytestmark = pytest.mark.host_integration


def test_daemon_install_relinks_existing_service_and_uninstall_removes_it(
    portforward_config,
    preserve_portforward_user_service,
) -> None:
    config_path, _vm_name, _host_local_port, _vm_remote_port, _vm_socks_port = portforward_config
    env_path = preserve_portforward_user_service["env_path"]
    unit_link = preserve_portforward_user_service["unit_link"]

    run_cli(["daemon", "install", "--config", str(config_path), "--non-interactive"], check=True)
    assert env_path.exists()
    env_contents = env_path.read_text(encoding="utf-8")
    assert f"AGSEKIT_BIN={_expected_agsekit_bin()}" in env_contents
    assert f"AGSEKIT_CONFIG={config_path.resolve()}" in env_contents
    assert f"AGSEKIT_PROJECT_DIR={REPO_ROOT.resolve()}" in env_contents
    assert unit_link.exists()
    assert unit_link.resolve() == (REPO_ROOT / "agsekit_cli" / "systemd" / "agsekit-portforward.service").resolve()

    wait_for(
        _systemd_is_active,
        timeout=60.0,
        message="daemon-backed service did not become active after install",
    )

    status_result = run_cli(["daemon", "status", "--non-interactive"], check=True)
    assert "Service: agsekit-portforward.service" in status_result.stdout
    assert "Active: active" in status_result.stdout

    run_cli(["daemon", "uninstall", "--non-interactive"], check=True)
    assert not unit_link.exists()



def test_daemon_start_stop_restart_manage_user_service(
    portforward_config,
    preserve_portforward_user_service,
) -> None:
    config_path, _vm_name, _host_local_port, _vm_remote_port, _vm_socks_port = portforward_config

    run_cli(["daemon", "install", "--config", str(config_path), "--non-interactive"], check=True)
    wait_for(
        _systemd_is_active,
        timeout=60.0,
        message="daemon-backed service did not become active after install",
    )

    initial_invocation_id = _systemd_invocation_id()
    assert initial_invocation_id

    run_cli(["daemon", "stop", "--non-interactive"], check=True)
    wait_for(
        lambda: not _systemd_is_active(),
        timeout=60.0,
        message="daemon-backed service did not stop after daemon stop",
    )

    run_cli(["daemon", "start", "--non-interactive"], check=True)
    wait_for(
        _systemd_is_active,
        timeout=60.0,
        message="daemon-backed service did not become active after daemon start",
    )

    started_invocation_id = _systemd_invocation_id()
    assert started_invocation_id
    assert started_invocation_id != initial_invocation_id

    run_cli(["daemon", "restart", "--non-interactive"], check=True)
    wait_for(
        lambda: _systemd_is_active() and _systemd_invocation_id() != started_invocation_id,
        timeout=60.0,
        message="daemon-backed service did not restart after daemon restart",
    )

    status_result = run_cli(["daemon", "status", "--non-interactive"], check=True)
    assert "Active: active" in status_result.stdout

    run_cli(["daemon", "uninstall", "--non-interactive"], check=True)
