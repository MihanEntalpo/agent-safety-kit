from __future__ import annotations

import signal
import socket
from pathlib import Path

import pytest

from tests.integration.utils import (
    REPO_ROOT,
    random_vm_name,
    require_host_tools,
    run_cmd,
    run_cli,
    skip_if_systemd_user_unavailable,
    start_cli,
    wait_for,
    write_config,
)


pytestmark = pytest.mark.host_integration


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    require_host_tools()
    run_cli(["prepare", "--non-interactive"], check=True)


def _allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def portforward_config(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("portforward")
    vm_name = random_vm_name("it-port")
    host_local_port = _allocate_port()
    host_remote_port = _allocate_port()
    vm_remote_port = _allocate_port()
    vm_socks_port = _allocate_port()
    config_path = tmp_path / "config.yaml"
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
                    },
                    {
                        "type": "remote",
                        "host-addr": f"127.0.0.1:{host_remote_port}",
                        "vm-addr": f"127.0.0.1:{vm_remote_port}",
                    },
                    {
                        "type": "socks5",
                        "vm-addr": f"127.0.0.1:{vm_socks_port}",
                    },
                ],
            }
        }
    }
    write_config(config_path, payload)
    run_cli(["create-vm", vm_name, "--config", str(config_path), "--non-interactive"], check=True)
    try:
        yield config_path, vm_name, host_local_port, vm_remote_port, vm_socks_port
    finally:
        run_cmd(["multipass", "delete", vm_name], check=False)
        run_cmd(["multipass", "purge"], check=False)


def _start_http_server(vm_name: str) -> str:
    result = run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            "nohup python3 -m http.server 8000 --bind 127.0.0.1 >/tmp/http.log 2>&1 & echo $!",
        ],
        check=True,
    )
    return result.stdout.strip()


def _stop_vm_process(vm_name: str, pid: str) -> None:
    if not pid:
        return
    run_cmd(["multipass", "exec", vm_name, "--", "bash", "-lc", f"kill {pid}"], check=False)


def _host_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def _vm_port_listening(vm_name: str, port: int) -> bool:
    result = run_cmd(
        ["multipass", "exec", vm_name, "--", "bash", "-lc", "ss -ltn"],
        check=True,
    )
    return f":{port} " in result.stdout


def test_portforward_rules_start_forwarders(portforward_config) -> None:
    config_path, vm_name, host_local_port, vm_remote_port, vm_socks_port = portforward_config
    http_pid = _start_http_server(vm_name)
    process = start_cli(["portforward", "--config", str(config_path), "--non-interactive"])
    try:
        wait_for(
            lambda: _host_port_open(host_local_port),
            timeout=60.0,
            message="local port forward did not start listening",
        )
        wait_for(
            lambda: _vm_port_listening(vm_name, vm_remote_port),
            timeout=60.0,
            message="remote port forward did not open VM port",
        )
        wait_for(
            lambda: _host_port_open(vm_socks_port),
            timeout=60.0,
            message="socks5 port forward did not open host port",
        )
    finally:
        process.send_signal(signal.SIGINT)
        process.wait(timeout=15)
        _stop_vm_process(vm_name, http_pid)


def test_systemd_install_and_uninstall(portforward_config) -> None:
    skip_if_systemd_user_unavailable()
    config_path, _vm_name, _host_local_port, _vm_remote_port, _vm_socks_port = portforward_config
    env_path = Path.home() / ".config" / "agsekit" / "systemd.env"
    unit_link = Path.home() / ".config" / "systemd" / "user" / "agsekit-portforward.service"

    run_cli(["systemd", "install", "--config", str(config_path), "--non-interactive"], check=True)
    assert env_path.exists()
    env_contents = env_path.read_text(encoding="utf-8")
    assert f"AGSEKIT_CONFIG={config_path.resolve()}" in env_contents
    assert unit_link.exists()

    run_cli(["systemd", "uninstall", "--non-interactive"], check=True)
    assert not unit_link.exists()
