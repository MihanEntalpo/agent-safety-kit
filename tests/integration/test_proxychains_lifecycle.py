from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

import pytest
import yaml


pytestmark = pytest.mark.host_integration

REPO_ROOT = Path(__file__).resolve().parents[2]


def _clean_env(overrides: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "PROXYCHAINS_CONF_FILE"):
        env.pop(key, None)
    venv_bin = str(Path(sys.executable).resolve().parent)
    env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
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
    env = _clean_env()
    env["AGSEKIT_LANG"] = "en"
    return _run([sys.executable, str(REPO_ROOT / "agsekit"), *args], check=check, cwd=cwd or REPO_ROOT, env=env)


def _start_cli(args: list[str], cwd: Optional[Path] = None) -> subprocess.Popen[str]:
    env = _clean_env()
    env["AGSEKIT_LANG"] = "en"
    return subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "agsekit"), *args],
        cwd=cwd or REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


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


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _instance_exists(name: str) -> bool:
    result = _run(["multipass", "list", "--format", "json"], check=True)
    payload = json.loads(result.stdout)
    return any(entry.get("name") == name for entry in payload.get("list", []))


def _delete_if_exists(name: str) -> None:
    if not _instance_exists(name):
        return
    _run(["multipass", "delete", name], check=False)
    _run(["multipass", "purge"], check=False)


def _write_config(
    config_path: Path,
    vm_name: str,
    socks_port: int,
    vm_proxychains_url: Optional[str],
    agent_proxychains_url: Optional[str] = None,
) -> None:
    vm_entry: dict[str, object] = {
        "cpu": 1,
        "ram": "1G",
        "disk": "5G",
        "port-forwarding": [
            {
                "type": "socks5",
                "vm-addr": f"0.0.0.0:{socks_port}",
            }
        ],
    }
    if vm_proxychains_url is not None:
        vm_entry["proxychains"] = vm_proxychains_url

    agent_entry: dict[str, object] = {
        "type": "qwen",
        "vm": vm_name,
    }
    if agent_proxychains_url is not None:
        agent_entry["proxychains"] = agent_proxychains_url
    payload = {
        "vms": {vm_name: vm_entry},
        "agents": {
            "qwen": agent_entry
        },
    }
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _vm_ip(vm_name: str) -> str:
    result = _run(["multipass", "info", vm_name, "--format", "json"], check=True)
    payload = json.loads(result.stdout)
    entry = payload.get("info", {}).get(vm_name, {})
    ips = entry.get("ipv4")
    if isinstance(ips, list) and ips:
        return str(ips[0])
    if isinstance(ips, str) and ips:
        return ips
    raise AssertionError(f"Unable to resolve IPv4 for VM {vm_name}")


def _vm_gateway_ip(vm_name: str) -> str:
    result = _run(
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
        raise AssertionError(f"Unable to resolve default gateway inside VM {vm_name}")
    return gateway


def _install_dummy_qwen(vm_name: str, endpoint: str) -> None:
    script = """#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import sys
import urllib.request

urllib.request.urlopen(%s, timeout=5).read(1)
PY
""" % repr(endpoint)
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    _run(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            (
                f"echo {shlex.quote(encoded)} | base64 -d | "
                "sudo tee /usr/local/bin/qwen >/dev/null && sudo chmod +x /usr/local/bin/qwen"
            ),
        ],
        check=True,
    )


def _start_http_server(vm_name: str, port: int) -> None:
    _run(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            (
                f"if [ -f /tmp/it-proxy-http.pid ]; then kill $(cat /tmp/it-proxy-http.pid) >/dev/null 2>&1 || true; fi; "
                f"nohup python3 -m http.server {port} --bind 0.0.0.0 "
                ">/tmp/it-proxy-http.log 2>&1 < /dev/null & echo $! > /tmp/it-proxy-http.pid"
            ),
        ],
        check=True,
    )


def _stop_http_server(vm_name: str) -> None:
    _run(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            "if [ -f /tmp/it-proxy-http.pid ]; then kill $(cat /tmp/it-proxy-http.pid) >/dev/null 2>&1 || true; fi",
        ],
        check=False,
    )


def _wait_for(predicate: Callable[[], bool], timeout: float, message: str, interval: float = 0.2) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError(message)


def _http_server_reachable_from_vm(vm_name: str, url: str) -> bool:
    result = _run(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            f"python3 -c \"import urllib.request; urllib.request.urlopen('{url}', timeout=2).read(1)\"",
        ],
        check=False,
    )
    return result.returncode == 0


def _is_tcp_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _run_agent(config_path: Path, cli_proxychains_url: Optional[str] = None) -> subprocess.CompletedProcess[str]:
    args = [
        "run",
        "qwen",
        "--config",
        str(config_path),
        "--disable-backups",
        "--non-interactive",
        "--debug",
    ]
    if cli_proxychains_url is not None:
        args.extend(["--proxychains", cli_proxychains_url])
    return _run_cli(args, check=False)


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    _require_host_tools()
    if shutil.which("multipass") is None:
        _run_cli(["prepare", "--non-interactive"], check=True)
    check = _run(["multipass", "version"], check=False)
    _skip_if_multipass_unusable(check)
    if check.returncode != 0:
        pytest.skip(check.stderr or check.stdout or "multipass is not ready")


def test_run_proxychains_priority_vm_agent_cli(tmp_path: Path) -> None:
    vm_name = _random_name("it-proxy-vm")
    socks_port = _pick_free_port()
    http_port = _pick_free_port()
    config_path = tmp_path / "config.yaml"

    portforward_proc: Optional[subprocess.Popen[str]] = None
    try:
        _write_config(config_path, vm_name, socks_port, vm_proxychains_url=None)
        create_result = _run_cli(
            ["create-vm", vm_name, "--config", str(config_path), "--non-interactive", "--debug"],
            check=False,
        )
        assert create_result.returncode == 0, create_result.stderr or create_result.stdout

        vm_ip = _vm_ip(vm_name)
        vm_gateway = _vm_gateway_ip(vm_name)
        working_proxy = f"socks5://{vm_gateway}:{socks_port}"

        endpoint = f"http://{vm_ip}:{http_port}"
        _install_dummy_qwen(vm_name, endpoint)
        _start_http_server(vm_name, http_port)
        _wait_for(
            lambda: _http_server_reachable_from_vm(vm_name, endpoint),
            timeout=20.0,
            message="HTTP server inside VM did not start in time",
        )

        portforward_proc = _start_cli(["portforward", "--config", str(config_path), "--non-interactive", "--debug"])
        _wait_for(
            lambda: _is_tcp_port_open("127.0.0.1", socks_port),
            timeout=20.0,
            message="SOCKS proxy port did not open on host",
        )

        dead_proxy_port = _pick_free_port()
        assert not _is_tcp_port_open("127.0.0.1", dead_proxy_port)
        dead_proxy = f"socks5://{vm_gateway}:{dead_proxy_port}"

        # 1) vm proxychains is used when agent/cli are not set.
        _write_config(
            config_path,
            vm_name,
            socks_port,
            vm_proxychains_url=working_proxy,
            agent_proxychains_url=None,
        )
        run_vm_only = _run_agent(config_path)
        assert run_vm_only.returncode == 0, run_vm_only.stderr or run_vm_only.stdout

        # 2) agent proxychains overrides vm proxychains.
        _write_config(
            config_path,
            vm_name,
            socks_port,
            vm_proxychains_url=dead_proxy,
            agent_proxychains_url=working_proxy,
        )
        run_agent_over_vm = _run_agent(config_path)
        assert run_agent_over_vm.returncode == 0, run_agent_over_vm.stderr or run_agent_over_vm.stdout

        # 3) cli --proxychains overrides agent/vm proxychains.
        _write_config(
            config_path,
            vm_name,
            socks_port,
            vm_proxychains_url=dead_proxy,
            agent_proxychains_url=dead_proxy,
        )
        run_cli_over_agent_vm = _run_agent(config_path, cli_proxychains_url=working_proxy)
        assert run_cli_over_agent_vm.returncode == 0, run_cli_over_agent_vm.stderr or run_cli_over_agent_vm.stdout

        # 4) cli --proxychains has highest priority even when vm+agent are working.
        _write_config(
            config_path,
            vm_name,
            socks_port,
            vm_proxychains_url=working_proxy,
            agent_proxychains_url=working_proxy,
        )
        run_cli_has_highest_priority = _run_agent(config_path, cli_proxychains_url=dead_proxy)
        assert run_cli_has_highest_priority.returncode != 0
    finally:
        if portforward_proc is not None:
            _stop_process(portforward_proc)
        _stop_http_server(vm_name)
        _delete_if_exists(vm_name)
