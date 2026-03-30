from __future__ import annotations

import json
import signal
import socket
from pathlib import Path
from typing import Any, Dict, Optional

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


def _systemd_is_active() -> bool:
    result = run_cmd(
        ["systemctl", "--user", "is-active", "agsekit-portforward"],
        check=False,
        env=clean_env(),
    )
    return result.returncode == 0


def _systemd_invocation_id() -> str:
    result = run_cmd(
        ["systemctl", "--user", "show", "agsekit-portforward", "--property", "InvocationID", "--value"],
        check=True,
        env=clean_env(),
    )
    return result.stdout.strip()


def _rewrite_portforward_config(
    config_path: Path,
    *,
    global_config: Optional[Dict[str, Any]] = None,
    vms: Dict[str, Dict[str, Any]],
) -> None:
    payload = {"vms": vms}
    if global_config is not None:
        payload["global"] = global_config
    write_config(config_path, payload)


def _vm_ip(vm_name: str) -> str:
    result = run_cmd(["multipass", "info", vm_name, "--format", "json"], check=True)
    payload = json.loads(result.stdout)
    return str(payload["info"][vm_name]["ipv4"][0])


def _ssh_via_custom_key(private_key: Path, vm_name: str) -> str:
    result = run_cmd(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-i",
            str(private_key),
            f"ubuntu@{_vm_ip(vm_name)}",
            "printf",
            "ok",
        ],
        check=True,
    )
    return result.stdout.strip()


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
    assert unit_link.resolve() == (REPO_ROOT / "agsekit_cli" / "systemd" / "agsekit-portforward.service").resolve()
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


def test_systemd_start_stop_restart_manage_user_service(
    portforward_config,
    preserve_portforward_user_service,
) -> None:
    config_path, _vm_name, _host_local_port, _vm_remote_port, _vm_socks_port = portforward_config

    run_cli(["systemd", "install", "--config", str(config_path), "--non-interactive"], check=True)
    wait_for(
        _systemd_is_active,
        timeout=60.0,
        message="systemd service did not become active after install",
    )

    initial_invocation_id = _systemd_invocation_id()
    assert initial_invocation_id

    run_cli(["systemd", "stop", "--non-interactive"], check=True)
    wait_for(
        lambda: not _systemd_is_active(),
        timeout=60.0,
        message="systemd service did not stop after systemd stop",
    )

    run_cli(["systemd", "start", "--non-interactive"], check=True)
    wait_for(
        _systemd_is_active,
        timeout=60.0,
        message="systemd service did not become active after systemd start",
    )

    started_invocation_id = _systemd_invocation_id()
    assert started_invocation_id
    assert started_invocation_id != initial_invocation_id

    run_cli(["systemd", "restart", "--non-interactive"], check=True)
    wait_for(
        lambda: _systemd_is_active() and _systemd_invocation_id() != started_invocation_id,
        timeout=60.0,
        message="systemd service did not restart after systemd restart",
    )

    status_result = run_cli(["systemd", "status", "--non-interactive"], check=True)
    assert "Active: active" in status_result.stdout

    run_cli(["systemd", "uninstall", "--non-interactive"], check=True)


def test_global_ssh_keys_folder_and_systemd_env_folder_are_used(
    tmp_path: Path,
    preserve_portforward_user_service,
) -> None:
    vm_name = random_vm_name("it-global")
    ssh_dir = tmp_path / "custom-ssh"
    env_dir = tmp_path / "custom-env"
    config_path = tmp_path / "config.yaml"
    default_env_path = preserve_portforward_user_service["env_path"]
    unit_link = preserve_portforward_user_service["unit_link"]

    write_config(
        config_path,
        {
            "global": {
                "ssh_keys_folder": str(ssh_dir),
                "systemd_env_folder": str(env_dir),
                "portforward_config_check_interval_sec": 2,
            },
            "vms": {
                vm_name: {
                    "cpu": 1,
                    "ram": "1G",
                    "disk": "5G",
                }
            },
        },
    )

    try:
        run_cli(["create-vm", vm_name, "--config", str(config_path), "--non-interactive"], check=True)

        private_key = ssh_dir / "id_rsa"
        public_key = ssh_dir / "id_rsa.pub"
        assert private_key.exists()
        assert public_key.exists()
        assert _ssh_via_custom_key(private_key, vm_name) == "ok"

        run_cli(["systemd", "install", "--config", str(config_path), "--non-interactive"], check=True)
        custom_env_path = env_dir / "systemd.env"
        assert custom_env_path.exists()
        env_contents = custom_env_path.read_text(encoding="utf-8")
        assert f"AGSEKIT_CONFIG={config_path.resolve()}" in env_contents
        assert f"AGSEKIT_PROJECT_DIR={REPO_ROOT.resolve()}" in env_contents
        assert default_env_path.is_symlink()
        assert default_env_path.resolve() == custom_env_path.resolve()
        assert unit_link.exists()
    finally:
        run_cli(["systemd", "uninstall", "--non-interactive"], check=False)
        run_cmd(["multipass", "delete", vm_name], check=False)
        run_cmd(["multipass", "purge"], check=False)


def test_portforward_reloads_config_and_reconciles_forwarders(tmp_path: Path) -> None:
    vm_one = random_vm_name("it-reload-a")
    vm_two = random_vm_name("it-reload-b")
    host_port_one = _allocate_port()
    host_port_two = _allocate_port()
    host_port_three = _allocate_port()
    config_path = tmp_path / "config.yaml"
    global_config = {"portforward_config_check_interval_sec": 2}

    setup_config_path = tmp_path / "setup-config.yaml"
    write_config(
        setup_config_path,
        {
            "global": global_config,
            "vms": {
                vm_one: {"cpu": 1, "ram": "1G", "disk": "5G"},
                vm_two: {"cpu": 1, "ram": "1G", "disk": "5G"},
            },
        },
    )
    run_cli(["create-vms", "--config", str(setup_config_path), "--non-interactive"], check=True)

    _rewrite_portforward_config(
        config_path,
        global_config=global_config,
        vms={
            vm_one: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
                "port-forwarding": [
                    {
                        "type": "local",
                        "host-addr": f"127.0.0.1:{host_port_one}",
                        "vm-addr": "127.0.0.1:8000",
                    }
                ],
            }
        },
    )

    vm_one_http_pid = _start_http_server(vm_one)
    vm_two_http_pid = _start_http_server(vm_two)
    process = start_cli(["portforward", "--config", str(config_path), "--non-interactive"])

    try:
        wait_for(
            lambda: _host_port_open(host_port_one),
            timeout=60.0,
            message="initial local port forward did not start listening",
        )

        _rewrite_portforward_config(
            config_path,
            global_config=global_config,
            vms={
                vm_one: {
                    "cpu": 1,
                    "ram": "1G",
                    "disk": "5G",
                    "port-forwarding": [
                        {
                            "type": "local",
                            "host-addr": f"127.0.0.1:{host_port_two}",
                            "vm-addr": "127.0.0.1:8000",
                        }
                    ],
                },
                vm_two: {
                    "cpu": 1,
                    "ram": "1G",
                    "disk": "5G",
                    "port-forwarding": [
                        {
                            "type": "local",
                            "host-addr": f"127.0.0.1:{host_port_three}",
                            "vm-addr": "127.0.0.1:8000",
                        }
                    ],
                },
            },
        )

        wait_for(
            lambda: _host_port_open(host_port_two),
            timeout=60.0,
            message="updated port forward for first VM did not start listening",
        )
        wait_for(
            lambda: _host_port_open(host_port_three),
            timeout=60.0,
            message="port forward for newly added VM did not start listening",
        )
        wait_for(
            lambda: not _host_port_open(host_port_one),
            timeout=60.0,
            message="stale port forward for first VM was not removed after config reload",
        )

        _rewrite_portforward_config(
            config_path,
            global_config=global_config,
            vms={
                vm_two: {
                    "cpu": 1,
                    "ram": "1G",
                    "disk": "5G",
                    "port-forwarding": [],
                }
            },
        )

        wait_for(
            lambda: not _host_port_open(host_port_two),
            timeout=60.0,
            message="forwarder for removed VM was not stopped after config reload",
        )
        wait_for(
            lambda: not _host_port_open(host_port_three),
            timeout=60.0,
            message="forwarder for VM with removed last port was not stopped after config reload",
        )
    finally:
        process.send_signal(signal.SIGINT)
        process.wait(timeout=15)
        _stop_vm_process(vm_one, vm_one_http_pid)
        _stop_vm_process(vm_two, vm_two_http_pid)
        run_cmd(["multipass", "delete", vm_one], check=False)
        run_cmd(["multipass", "delete", vm_two], check=False)
        run_cmd(["multipass", "purge"], check=False)
