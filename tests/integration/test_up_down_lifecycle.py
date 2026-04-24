from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Optional

import pytest

from tests.integration.utils import clean_env, random_vm_name, require_host_tools, run_cli, run_cmd, wait_for, write_config


pytestmark = pytest.mark.host_integration

SERVICE_NAME = "agsekit-portforward"


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    require_host_tools()
    run_cli(["prepare", "--non-interactive"], check=True)


def _allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _host_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def _instance_state(name: str) -> Optional[str]:
    result = run_cmd(["multipass", "list", "--format", "json"], check=True)
    payload = json.loads(result.stdout)
    for entry in payload.get("list", []):
        if entry.get("name") == name:
            state = entry.get("state")
            return str(state).lower() if state else None
    return None


def _service_is_active() -> bool:
    result = run_cmd(
        ["systemctl", "--user", "is-active", SERVICE_NAME],
        check=False,
        env=clean_env(),
    )
    return result.returncode == 0


def test_up_and_down_manage_vm_and_portforward_service(tmp_path, preserve_portforward_user_service) -> None:
    vm_name = random_vm_name("it-updown")
    host_local_port = _allocate_port()
    config_path = tmp_path / "config.yaml"
    env_path = preserve_portforward_user_service["env_path"]
    unit_link = preserve_portforward_user_service["unit_link"]

    payload = {
        "vms": {
            vm_name: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
                "port-forwarding": [
                    {
                        "type": "local",
                        "host-addr": f"127.0.0.1:{host_local_port}",
                        "vm-addr": "127.0.0.1:8000",
                    }
                ],
            }
        },
        "agents": {},
    }
    write_config(config_path, payload)

    try:
        up_result = run_cli(
            ["up", "--config", str(config_path), "--no-prepare", "--no-install-agents", "--non-interactive"],
            check=True,
        )

        assert "Setup completed successfully" in up_result.stdout
        wait_for(lambda: _instance_state(vm_name) == "running", timeout=240.0, message="VM was not running after up")
        wait_for(_service_is_active, timeout=90.0, message="portforward service did not become active after up")
        assert env_path.exists()
        env_contents = env_path.read_text(encoding="utf-8")
        assert f"AGSEKIT_BIN={(Path.cwd().resolve() / "agsekit").resolve()}" in env_contents
        assert f"AGSEKIT_CONFIG={config_path.resolve()}" in env_contents
        assert f"AGSEKIT_PROJECT_DIR={Path.cwd().resolve()}" in env_contents
        assert unit_link.exists()
        assert unit_link.resolve() == (
            Path.cwd().resolve() / "agsekit_cli" / "systemd" / "agsekit-portforward.service"
        ).resolve()

        down_result = run_cli(
            ["down", "--config", str(config_path), "--force", "--non-interactive"],
            check=True,
        )

        assert f"VM `{vm_name}` stopped." in down_result.stdout
        wait_for(
            lambda: _instance_state(vm_name) in {"stopped", "suspended"},
            timeout=120.0,
            message="VM was not stopped after down",
        )
        wait_for(lambda: not _service_is_active(), timeout=60.0, message="portforward service did not stop after down")
        assert unit_link.exists()
    finally:
        run_cmd(["multipass", "delete", vm_name], check=False)
        run_cmd(["multipass", "purge"], check=False)
