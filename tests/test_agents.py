from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.agents as agents
from agsekit_cli.config import PortForwardingRule, VmConfig


def test_run_in_vm_uses_cd_and_no_workdir_flag(monkeypatch):
    calls = {}

    def fake_run(args, check):
        calls["args"] = args

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(agents, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(agents.subprocess, "run", fake_run)

    workdir = Path("/home/ubuntu/project")
    env_vars = {"TOKEN": "abc"}

    vm_config = VmConfig(
        name="agent-vm",
        cpu=2,
        ram="2G",
        disk="10G",
        cloud_init={},
        port_forwarding=[
            PortForwardingRule(type="local", host_addr="127.0.0.1:8080", vm_addr="127.0.0.1:80"),
            PortForwardingRule(type="socks5", host_addr=None, vm_addr="127.0.0.1:8088"),
        ],
    )

    exit_code = agents.run_in_vm(vm_config, workdir, ["qwen", "--flag"], env_vars)

    assert exit_code == 0
    args = calls["args"]
    assert args[:3] == ["multipass", "ssh", "agent-vm"]
    assert "-L" in args and "-R" not in args
    assert "-D" in args
    assert args[-1].startswith("export NVM_DIR=")
    assert f"cd {workdir}" in args[-1]
    assert "qwen --flag" in args[-1]


def test_run_in_vm_wraps_with_proxypass(monkeypatch):
    calls = {}

    def fake_run(args, check):
        calls["args"] = args

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(agents, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(agents.subprocess, "run", fake_run)

    workdir = Path("/home/ubuntu/project")
    env_vars = {}

    vm_config = VmConfig(
        name="agent-vm",
        cpu=2,
        ram="2G",
        disk="10G",
        cloud_init={},
        port_forwarding=[],
        proxypass="socks5://127.0.0.1:8080",
    )

    agents.run_in_vm(vm_config, workdir, ["qwen"], env_vars)

    args = calls["args"]
    assert args[:2] == ["proxypass4", "socks5://127.0.0.1:8080"]
    assert args[2:5] == ["--", "multipass", "ssh"]

    calls.clear()
    agents.run_in_vm(vm_config, workdir, ["qwen"], env_vars, proxypass="")
    args = calls["args"]
    assert args[0] == "multipass"
