from __future__ import annotations

import signal
import socket
from pathlib import Path

import pytest

from agsekit_cli.commands.systemd import _resolve_agsekit_bin
from tests.integration.utils import (
    REPO_ROOT,
    clean_env,
    random_vm_name,
    require_host_tools,
    run_cmd,
    run_cli,
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


def test_systemd_install_relinks_existing_service_and_uninstall_removes_it(
    portforward_config,
    preserve_portforward_user_service,
) -> None:
    config_path, _vm_name, _host_local_port, _vm_remote_port, _vm_socks_port = portforward_config
    env_path = preserve_portforward_user_service["env_path"]
    unit_link = preserve_portforward_user_service["unit_link"]
    stale_root = config_path.parent / "stale-install"
    stale_unit = stale_root / "systemd" / "agsekit-portforward.service"
    stale_unit.parent.mkdir(parents=True, exist_ok=True)
    stale_unit.write_text("[Unit]\nDescription=stale\n", encoding="utf-8")
    unit_link.parent.mkdir(parents=True, exist_ok=True)
    if unit_link.exists() or unit_link.is_symlink():
        unit_link.unlink()
    unit_link.symlink_to(stale_unit)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        "AGSEKIT_BIN=/tmp/old-agsekit\nAGSEKIT_CONFIG=/tmp/old-config.yaml\nAGSEKIT_PROJECT_DIR=/tmp/old-project\n",
        encoding="utf-8",
    )
    run_cmd(["systemctl", "--user", "daemon-reload"], check=False, env=clean_env())

    run_cli(["systemd", "install", "--config", str(config_path), "--non-interactive"], check=True)
    assert env_path.exists()
    env_contents = env_path.read_text(encoding="utf-8")
    assert f"AGSEKIT_BIN={_resolve_agsekit_bin().resolve()}" in env_contents
    assert f"AGSEKIT_CONFIG={config_path.resolve()}" in env_contents
    assert f"AGSEKIT_PROJECT_DIR={REPO_ROOT.resolve()}" in env_contents
    assert unit_link.exists()
    assert unit_link.resolve() == (REPO_ROOT / "systemd" / "agsekit-portforward.service").resolve()
    active_result = run_cmd(
        ["systemctl", "--user", "is-active", "agsekit-portforward"],
        check=False,
        env=clean_env(),
    )
    if active_result.returncode != 0:
        wait_for(
            lambda: run_cmd(
                ["systemctl", "--user", "is-active", "agsekit-portforward"],
                check=False,
                env=clean_env(),
            ).returncode
            == 0,
            timeout=60.0,
            message="systemd service did not become active after install",
        )

    run_cli(["systemd", "uninstall", "--non-interactive"], check=True)
    assert not unit_link.exists()
