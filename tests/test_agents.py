from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.agents as agents
from agsekit_cli.config import AgentConfig, PortForwardingRule, VmConfig


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
    assert args[:3] == ["multipass", "exec", "agent-vm"]
    assert args[-1].startswith("export NVM_DIR=")
    assert f"cd {workdir}" in args[-1]
    assert "qwen --flag" in args[-1]


def test_run_in_vm_wraps_with_proxychains(monkeypatch):
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
        proxychains="socks5://127.0.0.1:1080",
    )

    monkeypatch.setattr(agents, "ensure_proxychains_runner", lambda _vm: "/tmp/agsekit-run_with_proxychains.sh")

    agents.run_in_vm(vm_config, workdir, ["qwen"], env_vars)

    args = calls["args"]
    assert args[:3] == ["multipass", "exec", "agent-vm"]
    assert args[3:6] == ["--", "bash", "-lc"]
    assert "bash /tmp/agsekit-run_with_proxychains.sh --proxy socks5://127.0.0.1:1080 --" in args[6]

    calls.clear()
    agents.run_in_vm(vm_config, workdir, ["qwen"], env_vars, proxychains="")
    args = calls["args"]
    assert args[0] == "multipass"


def test_agent_command_sequence_skips_overridden_equals_args():
    agent = AgentConfig(
        name="qwen",
        type="qwen",
        env={},
        default_args=["--openai-api-key=default", "--flag"],
        vm_name=None,
    )

    command = agents.agent_command_sequence(
        agent,
        ["--openai-api-key=user", "--extra"],
    )

    assert command == ["qwen", "--flag", "--openai-api-key=user", "--extra"]


def test_agent_command_sequence_skips_overridden_split_args():
    agent = AgentConfig(
        name="qwen",
        type="qwen",
        env={},
        default_args=["--base-url", "https://default", "--mode", "fast"],
        vm_name=None,
    )

    command = agents.agent_command_sequence(
        agent,
        ["--base-url", "https://override"],
    )

    assert command == ["qwen", "--mode", "fast", "--base-url", "https://override"]


def test_agent_command_sequence_skips_overridden_flag_args():
    agent = AgentConfig(
        name="qwen",
        type="qwen",
        env={},
        default_args=["--trace", "--other"],
        vm_name=None,
    )

    command = agents.agent_command_sequence(agent, ["--trace"])

    assert command == ["qwen", "--other", "--trace"]


def test_agent_command_sequence_skips_overridden_inline_space_args():
    agent = AgentConfig(
        name="qwen",
        type="qwen",
        env={},
        default_args=["--region eu-west-1", "--mode", "fast"],
        vm_name=None,
    )

    command = agents.agent_command_sequence(agent, ["--region", "us-east-1"])

    assert command == ["qwen", "--mode", "fast", "--region", "us-east-1"]
