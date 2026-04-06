from __future__ import annotations

import base64
import json
import shlex
import signal
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from tests.integration.utils import (
    REPO_ROOT,
    clean_env,
    random_vm_name,
    require_host_tools,
    run_cli,
    run_cmd,
    start_cli,
    wait_for,
    write_config,
)


pytestmark = pytest.mark.host_integration

PROXY_ENV_OVERRIDES = {
    "HTTP_PROXY": "",
    "http_proxy": "",
    "HTTPS_PROXY": "",
    "https_proxy": "",
    "ALL_PROXY": "",
    "all_proxy": "",
    "NO_PROXY": "",
    "no_proxy": "",
}


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _vm_ip(vm_name: str) -> str:
    result = run_cmd(["multipass", "info", vm_name, "--format", "json"], check=True)
    payload = json.loads(result.stdout)
    ips = payload.get("info", {}).get(vm_name, {}).get("ipv4")
    if isinstance(ips, list) and ips:
        return str(ips[0])
    if isinstance(ips, str) and ips:
        return ips
    raise AssertionError("Unable to resolve IPv4 for VM {vm_name}".format(vm_name=vm_name))


def _vm_gateway_ip(vm_name: str) -> str:
    result = run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            "ip route show default | awk '/default/ {print $3; exit}'",
        ],
        check=True,
    )
    gateway = (result.stdout or "").strip()
    if not gateway:
        raise AssertionError("Unable to resolve default gateway inside VM {vm_name}".format(vm_name=vm_name))
    return gateway


def _install_dummy_aider(vm_name: str) -> None:
    script = """#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import os
import sys
import urllib.request

expected = os.environ.get("EXPECTED_HTTP_PROXY")
actual = os.environ.get("HTTP_PROXY")
actual_lower = os.environ.get("http_proxy")

if expected:
    if actual != expected:
        sys.stderr.write(f"unexpected HTTP_PROXY: {actual!r} != {expected!r}\\n")
        sys.exit(21)
    if actual_lower != expected:
        sys.stderr.write(f"unexpected http_proxy: {actual_lower!r} != {expected!r}\\n")
        sys.exit(22)

target_url = os.environ.get("TARGET_URL")
if target_url:
    with urllib.request.urlopen(target_url, timeout=10) as response:
        response.read(1)

sys.stdout.write((actual or "") + "\\n")
PY
"""
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            (
                "echo {encoded} | base64 -d | "
                "sudo tee /usr/local/bin/aider >/dev/null && sudo chmod +x /usr/local/bin/aider"
            ).format(encoded=shlex.quote(encoded)),
        ],
        check=True,
    )


def _start_http_server(vm_name: str, port: int, pid_path: str) -> None:
    run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            (
                "if [ -f {pid} ]; then kill $(cat {pid}) >/dev/null 2>&1 || true; fi; "
                "nohup python3 -m http.server {port} --bind 0.0.0.0 "
                ">/tmp/it-http-proxy-server.log 2>&1 < /dev/null & echo $! > {pid}"
            ).format(pid=shlex.quote(pid_path), port=port),
        ],
        check=True,
    )


def _stop_pid_file(vm_name: str, pid_path: str) -> None:
    run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            "if [ -f {pid} ]; then kill $(cat {pid}) >/dev/null 2>&1 || true; rm -f {pid}; fi".format(
                pid=shlex.quote(pid_path)
            ),
        ],
        check=False,
    )


def _remove_direct_privoxy_config(vm_name: str) -> None:
    run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            "sudo rm -f /etc/privoxy/it-direct-privoxy.conf",
        ],
        check=False,
    )


def _start_direct_privoxy(vm_name: str, listen_addr: str, pid_path: str) -> None:
    config_content = """confdir /etc/privoxy
templdir /etc/privoxy/templates
actionsfile match-all.action
actionsfile default.action
actionsfile user.action
filterfile default.filter
listen-address {listen_addr}
logdir /tmp/it-direct-privoxy/logdir
logfile logfile
toggle 1
enable-edit-actions 0
enable-remote-toggle 0
enable-remote-http-toggle 0
enforce-blocks 0
buffer-limit 4096
""".format(listen_addr=listen_addr)
    encoded = base64.b64encode(config_content.encode("utf-8")).decode("ascii")
    run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            (
                "mkdir -p /tmp/it-direct-privoxy/logdir && chmod 0755 /tmp/it-direct-privoxy && "
                "chmod 0777 /tmp/it-direct-privoxy/logdir && "
                "echo {encoded} | base64 -d > /tmp/it-direct-privoxy/config && chmod 0644 /tmp/it-direct-privoxy/config && "
                "sudo cp /tmp/it-direct-privoxy/config /etc/privoxy/it-direct-privoxy.conf && "
                "if [ -f {pid} ]; then kill $(cat {pid}) >/dev/null 2>&1 || true; fi; "
                "nohup sudo privoxy --no-daemon /etc/privoxy/it-direct-privoxy.conf "
                ">/tmp/it-direct-privoxy/stdout.log 2>&1 < /dev/null & echo $! > {pid}"
            ).format(encoded=shlex.quote(encoded), pid=shlex.quote(pid_path)),
        ],
        check=True,
    )


def _is_tcp_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _http_endpoint_reachable_from_vm(vm_name: str, url: str) -> bool:
    result = run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            "python3 -c \"import urllib.request; urllib.request.urlopen({url}, timeout=2).read(1)\"".format(
                url=repr(url)
            ),
        ],
        check=False,
    )
    return result.returncode == 0


def _stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _write_http_proxy_config(
    config_path: Path,
    vm_name: str,
    *,
    vm_proxychains: Optional[str] = None,
    vm_http_proxy: Any = None,
    agent_http_proxy: Any = None,
    agent_http_proxy_set: bool = False,
    agent_env: Optional[Dict[str, str]] = None,
    global_http_proxy_port_pool: Optional[Dict[str, int]] = None,
    socks_port: Optional[int] = None,
) -> None:
    vm_entry: Dict[str, Any] = {
        "cpu": 1,
        "ram": "1G",
        "disk": "6G",
    }
    if socks_port is not None:
        vm_entry["port-forwarding"] = [
            {
                "type": "socks5",
                "vm-addr": "0.0.0.0:{port}".format(port=socks_port),
            }
        ]
    if vm_proxychains is not None:
        vm_entry["proxychains"] = vm_proxychains
    if vm_http_proxy is not None:
        vm_entry["http_proxy"] = vm_http_proxy

    agent_entry: Dict[str, Any] = {
        "type": "aider",
        "vm": vm_name,
        "env": dict(agent_env or {}),
    }
    if agent_http_proxy_set:
        agent_entry["http_proxy"] = agent_http_proxy

    payload: Dict[str, Any] = {
        "vms": {
            vm_name: vm_entry,
        },
        "mounts": [
            {
                "source": str(REPO_ROOT),
                "vm": vm_name,
            }
        ],
        "agents": {
            "aider-http": agent_entry,
        },
    }
    if global_http_proxy_port_pool is not None:
        payload["global"] = {
            "http_proxy_port_pool": dict(global_http_proxy_port_pool),
        }
    write_config(config_path, payload)


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    require_host_tools()
    run_cli(["prepare", "--non-interactive"], check=True, env_overrides=PROXY_ENV_OVERRIDES)


@pytest.fixture(scope="module")
def http_proxy_env(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("http-proxy")
    vm_name = random_vm_name("it-http-proxy")
    config_path = tmp_path / "config.yaml"
    _write_http_proxy_config(config_path, vm_name)
    run_cli(
        ["create-vm", vm_name, "--config", str(config_path), "--non-interactive"],
        check=True,
        env_overrides=PROXY_ENV_OVERRIDES,
    )
    _install_dummy_aider(vm_name)
    try:
        yield {
            "config_path": config_path,
            "vm_name": vm_name,
            "vm_ip": _vm_ip(vm_name),
            "vm_gateway": _vm_gateway_ip(vm_name),
        }
    finally:
        _stop_pid_file(vm_name, "/tmp/it-http-proxy-server.pid")
        _stop_pid_file(vm_name, "/tmp/it-direct-privoxy.pid")
        _remove_direct_privoxy_config(vm_name)
        run_cmd(["multipass", "delete", vm_name], check=False, env=clean_env(PROXY_ENV_OVERRIDES))
        run_cmd(["multipass", "purge"], check=False, env=clean_env(PROXY_ENV_OVERRIDES))


def test_create_vm_installs_http_proxy_runtime_bits(http_proxy_env) -> None:
    vm_name = http_proxy_env["vm_name"]
    result = run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            "command -v privoxy >/dev/null && [ -x /usr/bin/agsekit-run_with_http_proxy.sh ]",
        ],
        check=True,
    )
    assert result.returncode == 0


def test_run_with_direct_http_proxy_url(http_proxy_env) -> None:
    config_path = http_proxy_env["config_path"]
    vm_name = http_proxy_env["vm_name"]
    vm_ip = http_proxy_env["vm_ip"]
    http_port = _pick_free_port()
    direct_proxy_port = _pick_free_port()
    proxy_url = "http://127.0.0.1:{port}".format(port=direct_proxy_port)

    _start_http_server(vm_name, http_port, "/tmp/it-http-proxy-server.pid")
    _start_direct_privoxy(vm_name, "127.0.0.1:{port}".format(port=direct_proxy_port), "/tmp/it-direct-privoxy.pid")
    wait_for(
        lambda: _http_endpoint_reachable_from_vm(
            vm_name,
            "http://{vm_ip}:{http_port}".format(vm_ip=vm_ip, http_port=http_port),
        ),
        timeout=20.0,
        message="HTTP endpoint inside VM did not start in time",
    )
    wait_for(
        lambda: run_cmd(
            [
                "multipass",
                "exec",
                vm_name,
                "--",
                "bash",
                "-lc",
                "python3 -c \"import socket; s=socket.create_connection(('127.0.0.1',{port}), 1); s.close()\"".format(
                    port=direct_proxy_port
                ),
            ],
            check=False,
        ).returncode
        == 0,
        timeout=20.0,
        message="Direct privoxy inside VM did not start in time",
    )

    _write_http_proxy_config(
        config_path,
        vm_name,
        vm_http_proxy={"url": proxy_url},
        agent_env={
            "TARGET_URL": "http://{vm_ip}:{http_port}".format(vm_ip=vm_ip, http_port=http_port),
            "EXPECTED_HTTP_PROXY": proxy_url,
        },
    )
    result = run_cli(
        ["run", "--config", str(config_path), "--disable-backups", "--auto-mount", "--non-interactive", "aider-http"],
        check=True,
        env_overrides=PROXY_ENV_OVERRIDES,
    )
    assert proxy_url in (result.stdout or "")


def test_run_with_upstream_http_proxy_uses_auto_pool_port(http_proxy_env) -> None:
    config_path = http_proxy_env["config_path"]
    vm_name = http_proxy_env["vm_name"]
    vm_ip = http_proxy_env["vm_ip"]
    vm_gateway = http_proxy_env["vm_gateway"]
    http_port = _pick_free_port()
    socks_port = _pick_free_port()
    pool_port = _pick_free_port()
    portforward_proc: Optional[subprocess.Popen[str]] = None

    try:
        _start_http_server(vm_name, http_port, "/tmp/it-http-proxy-server.pid")
        wait_for(
            lambda: _http_endpoint_reachable_from_vm(
                vm_name,
                "http://{vm_ip}:{http_port}".format(vm_ip=vm_ip, http_port=http_port),
            ),
            timeout=20.0,
            message="HTTP endpoint inside VM did not start in time",
        )
        _write_http_proxy_config(
            config_path,
            vm_name,
            vm_http_proxy="socks5://{gateway}:{port}".format(gateway=vm_gateway, port=socks_port),
            agent_env={
                "TARGET_URL": "http://{vm_ip}:{http_port}".format(vm_ip=vm_ip, http_port=http_port),
                "EXPECTED_HTTP_PROXY": "http://127.0.0.1:{port}".format(port=pool_port),
            },
            global_http_proxy_port_pool={"start": pool_port, "end": pool_port},
            socks_port=socks_port,
        )
        portforward_proc = start_cli(
            ["portforward", "--config", str(config_path), "--non-interactive"],
            env_overrides=PROXY_ENV_OVERRIDES,
        )
        wait_for(
            lambda: _is_tcp_port_open("127.0.0.1", socks_port),
            timeout=20.0,
            message="SOCKS portforward did not open on host",
        )
        result = run_cli(
            ["run", "--config", str(config_path), "--disable-backups", "--auto-mount", "--non-interactive", "aider-http"],
            check=True,
            env_overrides=PROXY_ENV_OVERRIDES,
        )
        assert "http://127.0.0.1:{port}".format(port=pool_port) in (result.stdout or "")
    finally:
        if portforward_proc is not None:
            _stop_process(portforward_proc)


def test_run_with_upstream_http_proxy_respects_explicit_listen(http_proxy_env) -> None:
    config_path = http_proxy_env["config_path"]
    vm_name = http_proxy_env["vm_name"]
    vm_ip = http_proxy_env["vm_ip"]
    vm_gateway = http_proxy_env["vm_gateway"]
    http_port = _pick_free_port()
    socks_port = _pick_free_port()
    listen_port = _pick_free_port()
    listen_addr = "127.0.0.1:{port}".format(port=listen_port)
    portforward_proc: Optional[subprocess.Popen[str]] = None

    try:
        _start_http_server(vm_name, http_port, "/tmp/it-http-proxy-server.pid")
        wait_for(
            lambda: _http_endpoint_reachable_from_vm(
                vm_name,
                "http://{vm_ip}:{http_port}".format(vm_ip=vm_ip, http_port=http_port),
            ),
            timeout=20.0,
            message="HTTP endpoint inside VM did not start in time",
        )
        _write_http_proxy_config(
            config_path,
            vm_name,
            agent_http_proxy={
                "upstream": "socks5://{gateway}:{port}".format(gateway=vm_gateway, port=socks_port),
                "listen": listen_addr,
            },
            agent_http_proxy_set=True,
            agent_env={
                "TARGET_URL": "http://{vm_ip}:{http_port}".format(vm_ip=vm_ip, http_port=http_port),
                "EXPECTED_HTTP_PROXY": "http://{listen}".format(listen=listen_addr),
            },
            socks_port=socks_port,
        )
        portforward_proc = start_cli(
            ["portforward", "--config", str(config_path), "--non-interactive"],
            env_overrides=PROXY_ENV_OVERRIDES,
        )
        wait_for(
            lambda: _is_tcp_port_open("127.0.0.1", socks_port),
            timeout=20.0,
            message="SOCKS portforward did not open on host",
        )
        result = run_cli(
            ["run", "--config", str(config_path), "--disable-backups", "--auto-mount", "--non-interactive", "aider-http"],
            check=True,
            env_overrides=PROXY_ENV_OVERRIDES,
        )
        assert "http://{listen}".format(listen=listen_addr) in (result.stdout or "")
    finally:
        if portforward_proc is not None:
            _stop_process(portforward_proc)


def test_run_rejects_effective_http_proxy_with_effective_proxychains(http_proxy_env) -> None:
    config_path = http_proxy_env["config_path"]
    vm_name = http_proxy_env["vm_name"]

    _write_http_proxy_config(
        config_path,
        vm_name,
        vm_proxychains="socks5://127.0.0.1:18080",
        agent_http_proxy={"url": "http://127.0.0.1:18881"},
        agent_http_proxy_set=True,
    )
    result = run_cli(
        ["run", "--config", str(config_path), "--disable-backups", "--auto-mount", "--non-interactive", "aider-http"],
        check=False,
        env_overrides=PROXY_ENV_OVERRIDES,
    )
    assert result.returncode != 0
    assert "HTTP proxy and runtime proxychains cannot be enabled at the same time" in (result.stderr or result.stdout or "")
