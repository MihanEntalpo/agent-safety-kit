from pathlib import Path
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.agents as agents
from agsekit_cli.agents_modules.base import AGENT_HOMES_ROOT
from agsekit_cli.config import AGENT_RUNTIME_BINARIES, AgentConfig, PortForwardingRule, VmConfig


def test_run_in_vm_uses_vm_side_wrapper(monkeypatch):
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
    assert args[3:6] == ["--", "bash", "-lc"]
    remote_command = args[6]
    assert agents.RUN_AGENT_RUNNER_PATH in remote_command
    assert "agsekit create-vms" in remote_command
    assert "else echo" in remote_command
    assert f"--workdir {workdir}" in remote_command
    assert "--binary qwen" in remote_command
    assert "grep -q -- '--allow-home-path'" in remote_command
    assert "--load-nvm" in remote_command
    assert "--allow-home-path .qwen" in remote_command
    assert "--env TOKEN=abc" in remote_command
    assert "-- qwen --flag" in remote_command
    assert "mkdir -p" not in remote_command


@pytest.mark.parametrize("binary", sorted(set(AGENT_RUNTIME_BINARIES.values())))
def test_run_in_vm_wraps_with_proxychains(monkeypatch, binary: str):
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

    agents.run_in_vm(vm_config, workdir, [binary], env_vars)

    args = calls["args"]
    assert args[:3] == ["multipass", "exec", "agent-vm"]
    assert args[3:6] == ["--", "bash", "-lc"]
    remote_command = args[6]
    assert agents.RUN_AGENT_RUNNER_PATH in remote_command
    assert "--proxychains socks5://127.0.0.1:1080" in remote_command
    assert f"-- {binary}" in remote_command

    calls.clear()
    agents.run_in_vm(vm_config, workdir, [binary], env_vars, proxychains="")
    args = calls["args"]
    remote_command = args[6]
    assert "--proxychains" not in remote_command


def test_agent_command_sequence_skips_overridden_equals_args():
    agent = AgentConfig(
        name="qwen",
        type="qwen",
        version="0.15.11",
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
        version="0.15.11",
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
        version="0.15.11",
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
        version="0.15.11",
        env={},
        default_args=["--region eu-west-1", "--mode", "fast"],
        vm_name=None,
    )

    command = agents.agent_command_sequence(agent, ["--region", "us-east-1"])

    assert command == ["qwen", "--mode", "fast", "--region", "us-east-1"]


def test_build_agent_env_merges_agent_defaults_with_configured_env():
    agent = AgentConfig(
        name="forgecode-main",
        type="forgecode",
        version="2.12.14",
        env={"TOKEN": "abc", "FORGE_TRACKER": "true"},
        vm_name=None,
    )

    env = agents.build_agent_env(agent)

    assert env["HOME"] == f"{AGENT_HOMES_ROOT}/forgecode-main"
    assert env["FORGE_CONFIG"] == f"{AGENT_HOMES_ROOT}/forgecode-main/forge"
    assert env["TOKEN"] == "abc"
    assert env["FORGE_TRACKER"] == "true"


def test_build_agent_env_sets_auto_update_env_defaults():
    aider_env = agents.build_agent_env(
        AgentConfig(name="aider", type="aider", version="0.86.2", env={}, vm_name=None)
    )
    opencode_env = agents.build_agent_env(
        AgentConfig(name="opencode", type="opencode", version="1.14.50", env={}, vm_name=None)
    )
    claude_env = agents.build_agent_env(
        AgentConfig(name="claude", type="claude", version="2.1.141", env={}, vm_name=None)
    )
    cline_env = agents.build_agent_env(
        AgentConfig(name="cline", type="cline", version="2.17.0", env={}, vm_name=None)
    )

    assert aider_env["AIDER_CHECK_UPDATE"] == "false"
    assert opencode_env["OPENCODE_DISABLE_AUTOUPDATE"] == "true"
    assert claude_env["DISABLE_AUTOUPDATER"] == "1"
    assert cline_env["CLINE_NO_AUTO_UPDATE"] == "1"


@pytest.mark.parametrize(("agent_type", "runtime_binary"), sorted(AGENT_RUNTIME_BINARIES.items()))
def test_agent_command_sequence_uses_runtime_binary(agent_type: str, runtime_binary: str):
    agent = AgentConfig(
        name=f"{agent_type}-main",
        type=agent_type,
        version="1.0.0",
        env={},
        default_args=["--verbose"],
        vm_name=None,
    )

    command = agents.agent_command_sequence(agent, ["--print"])

    assert command == [runtime_binary, "--verbose", "--print"]



def test_run_in_vm_passes_http_proxy_upstream_settings(monkeypatch):
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
        port_forwarding=[],
    )

    http_proxy = agents.HttpProxyConfig(upstream="socks5://127.0.0.1:18881", listen="127.0.0.1:8118")
    http_proxy_port_pool = agents.HttpProxyPortPoolConfig(start=21000, end=21010)

    agents.run_in_vm(
        vm_config,
        workdir,
        ["qwen", "--flag"],
        env_vars,
        http_proxy=http_proxy,
        http_proxy_port_pool=http_proxy_port_pool,
    )

    args = calls["args"]
    assert args[:3] == ["multipass", "exec", "agent-vm"]
    assert args[3:6] == ["--", "bash", "-lc"]
    remote_command = args[6]
    assert "--http-proxy-upstream socks5://127.0.0.1:18881" in remote_command
    assert "--http-proxy-listen 127.0.0.1:8118" in remote_command
    assert "--http-proxy-pool-start 21000" in remote_command
    assert "--http-proxy-pool-end 21010" in remote_command


def test_run_agent_wrapper_migrates_allowed_paths_from_legacy_home(tmp_path):
    legacy_home = tmp_path / "legacy-home"
    target_home = legacy_home / ".agent-homes" / "qwen-local"
    workdir = tmp_path / "project"
    bin_dir = tmp_path / "bin"
    legacy_qwen = legacy_home / ".qwen"

    legacy_qwen.mkdir(parents=True)
    (legacy_qwen / "settings.json").write_text("{}", encoding="utf-8")
    workdir.mkdir()
    bin_dir.mkdir()
    qwen_binary = bin_dir / "qwen"
    qwen_binary.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    qwen_binary.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(legacy_home)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

    script_path = ROOT / "agsekit_cli" / "run_agent.sh"
    result = subprocess.run(
        [
            "bash",
            str(script_path),
            "--workdir",
            str(workdir),
            "--binary",
            "qwen",
            "--allow-home-path",
            ".qwen",
            "--allow-home-path",
            "/absolute-is-ignored",
            "--allow-home-path",
            "../traversal-is-ignored",
            "--env",
            f"HOME={target_home}",
            "--",
            "qwen",
        ],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (target_home / ".qwen" / "settings.json").read_text(encoding="utf-8") == "{}"
    assert (target_home / ".agsekit-migrated-from-legacy-home").exists()
    assert not (target_home / "absolute-is-ignored").exists()
    assert not (legacy_home.parent / "traversal-is-ignored").exists()


def test_run_agent_wrapper_does_not_migrate_when_target_home_exists(tmp_path):
    legacy_home = tmp_path / "legacy-home"
    target_home = legacy_home / ".agent-homes" / "qwen-local"
    workdir = tmp_path / "project"
    bin_dir = tmp_path / "bin"

    (legacy_home / ".qwen").mkdir(parents=True)
    (legacy_home / ".qwen" / "settings.json").write_text("legacy", encoding="utf-8")
    (target_home / ".qwen").mkdir(parents=True)
    (target_home / ".qwen" / "settings.json").write_text("existing", encoding="utf-8")
    workdir.mkdir()
    bin_dir.mkdir()
    qwen_binary = bin_dir / "qwen"
    qwen_binary.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    qwen_binary.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(legacy_home)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

    script_path = ROOT / "agsekit_cli" / "run_agent.sh"
    result = subprocess.run(
        [
            "bash",
            str(script_path),
            "--workdir",
            str(workdir),
            "--binary",
            "qwen",
            "--allow-home-path",
            ".qwen",
            "--env",
            f"HOME={target_home}",
            "--",
            "qwen",
        ],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (target_home / ".qwen" / "settings.json").read_text(encoding="utf-8") == "existing"
    assert not (target_home / ".agsekit-migrated-from-legacy-home").exists()
