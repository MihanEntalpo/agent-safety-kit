import sys
import re
from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.status as status_module
from agsekit_cli.config import AGENT_RUNTIME_BINARIES
from agsekit_cli.commands.status import status_command


def _write_config(config_path: Path, source_dir: Path, backup_dir: Path) -> None:
    config_path.write_text(
        f"""
vms:
  agent:
    cpu: 2
    ram: 2G
    disk: 16G
    port-forwarding:
      - type: local
        host-addr: 127.0.0.1:80
        vm-addr: 127.0.0.1:1881
      - type: socks5
        vm-addr: 127.0.0.1:1080
mounts:
  - source: {source_dir}
    target: /home/ubuntu/project
    backup: {backup_dir}
    interval: 5
    max_backups: 100
    backup_clean_method: thin
    vm: agent
agents:
  qwen_main:
    type: qwen
    vm: agent
""",
        encoding="utf-8",
    )


def test_status_command_prints_vm_mount_agent_info(monkeypatch, tmp_path):
    source_dir = tmp_path / "project"
    source_dir.mkdir()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / datetime.now().strftime("%Y%m%d-%H%M%S")).mkdir()

    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source_dir, backup_dir)

    monkeypatch.setattr(
        status_module,
        "_load_multipass_entries",
        lambda: (
            {
                "agent": {
                    "name": "agent",
                    "state": "Running",
                    "cpus": 4,
                    "mem": "4G",
                    "disk": "16G",
                }
            },
            None,
        ),
    )
    monkeypatch.setattr(status_module, "_load_multipass_info_entries", lambda: ({}, None))
    monkeypatch.setattr(status_module, "_is_portforward_running", lambda: True)
    monkeypatch.setattr(status_module, "_check_agent_binary_installed", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        status_module,
        "_collect_running_agent_processes",
        lambda *_args, **_kwargs: [("321", "qwen", "/home/ubuntu/project")],
    )

    runner = CliRunner()
    result = runner.invoke(status_command, ["--config", str(config_path)], env={"AGSEKIT_LANG": "en"})

    assert result.exit_code == 0
    assert f"Config path: {config_path}" in result.output
    assert "VM: agent" in result.output
    assert "State: running" in result.output
    assert "CPU: 2 cores (real: 4 cores)" in result.output
    assert "Configured port forwarding: 80(host)-->1881(vm), socks(host)->1080(vm)" in result.output
    assert "Portforward process status: running" in result.output
    assert "qwen_main (qwen): installed" in result.output
    assert "PID 321: qwen (config name: qwen_main), folder: /home/ubuntu/project" in result.output


def test_status_command_fails_when_config_missing(tmp_path):
    missing_config = tmp_path / "missing.yaml"

    runner = CliRunner()
    result = runner.invoke(status_command, ["--config", str(missing_config)], env={"AGSEKIT_LANG": "en"})

    assert result.exit_code != 0
    assert f"Config path: {missing_config}" in result.output
    assert "Config file not found" in result.output


def test_status_command_uses_multipass_info_for_nested_resource_values(monkeypatch, tmp_path):
    source_dir = tmp_path / "project"
    source_dir.mkdir()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / datetime.now().strftime("%Y%m%d-%H%M%S")).mkdir()

    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source_dir, backup_dir)

    monkeypatch.setattr(
        status_module,
        "_load_multipass_entries",
        lambda: (
            {
                "agent": {
                    "name": "agent",
                    "state": "Running",
                }
            },
            None,
        ),
    )
    monkeypatch.setattr(
        status_module,
        "_load_multipass_info_entries",
        lambda: (
            {
                "agent": {
                    "cpu_count": 4,
                    "memory": {"usage": "512M", "total": "4G"},
                    "disks": {"sda1": {"used": "3G", "total": "20G"}},
                }
            },
            None,
        ),
    )
    monkeypatch.setattr(status_module, "_is_portforward_running", lambda: True)
    monkeypatch.setattr(status_module, "_check_agent_binary_installed", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        status_module,
        "_collect_running_agent_processes",
        lambda *_args, **_kwargs: [("321", "qwen", "/home/ubuntu/project")],
    )

    runner = CliRunner()
    result = runner.invoke(status_command, ["--config", str(config_path)], env={"AGSEKIT_LANG": "en"})

    assert result.exit_code == 0
    assert "CPU: 2 cores (real: 4 cores)" in result.output
    assert "RAM: 2G (real: 4.0 GB)" in result.output
    assert "Disk: 16G (real: 20.0 GB)" in result.output


def test_collect_running_agent_processes_filters_child_processes(monkeypatch):
    class Result:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    ps_output = "\n".join(
        [
            "4976 1 /usr/local/bin/codex-glibc --model x",
            "5294 4976 /usr/local/bin/codex-glibc --child",
            "7142 1 /usr/local/bin/qwen",
            "7462 7142 /usr/local/bin/qwen --worker",
            "8100 1 /usr/bin/bash",
        ]
    )

    def fake_run(command, check=False, capture_output=False, text=False):
        del check, capture_output, text
        if command[:7] == ["multipass", "exec", "agent", "--", "ps", "-eo", "pid=,ppid=,args="]:
            return Result(0, stdout=ps_output)
        if command[:5] == ["multipass", "exec", "agent", "--", "bash"]:
            script = command[-1]
            match = re.search(r"/proc/(\d+)/cwd", script)
            assert match is not None
            pid = match.group(1)
            cwd = "/home/ubuntu/project-a" if pid == "4976" else "/home/ubuntu/project-b"
            return Result(0, stdout=f"{cwd}\n")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(status_module.subprocess, "run", fake_run)

    result = status_module._collect_running_agent_processes("agent", ["codex-glibc", "qwen"])

    assert result == [
        ("4976", "codex-glibc", "/home/ubuntu/project-a"),
        ("7142", "qwen", "/home/ubuntu/project-b"),
    ]


def test_status_command_prints_plural_config_names(monkeypatch, tmp_path):
    source_dir = tmp_path / "project"
    source_dir.mkdir()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / datetime.now().strftime("%Y%m%d-%H%M%S")).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
vms:
  agent:
    cpu: 2
    ram: 2G
    disk: 16G
mounts:
  - source: {source_dir}
    target: /home/ubuntu/project
    backup: {backup_dir}
    interval: 5
    max_backups: 100
    backup_clean_method: thin
    vm: agent
agents:
  qwen_main:
    type: qwen
    vm: agent
  qwen_alt:
    type: qwen
    vm: agent
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(status_module, "_load_multipass_entries", lambda: ({"agent": {"state": "Running"}}, None))
    monkeypatch.setattr(status_module, "_load_multipass_info_entries", lambda: ({}, None))
    monkeypatch.setattr(status_module, "_is_portforward_running", lambda: True)
    monkeypatch.setattr(status_module, "_check_agent_binary_installed", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        status_module,
        "_collect_running_agent_processes",
        lambda *_args, **_kwargs: [("321", "qwen", "/home/ubuntu/project")],
    )

    runner = CliRunner()
    result = runner.invoke(status_command, ["--config", str(config_path)], env={"AGSEKIT_LANG": "en"})

    assert result.exit_code == 0
    assert "PID 321: qwen (config names: qwen_alt, qwen_main), folder: /home/ubuntu/project" in result.output


@pytest.mark.parametrize(("agent_type", "runtime_binary"), sorted(AGENT_RUNTIME_BINARIES.items()))
def test_status_command_uses_runtime_binary_for_agent_type(monkeypatch, tmp_path, agent_type: str, runtime_binary: str):
    agent_name = f"{agent_type}_main"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
vms:
  agent:
    cpu: 2
    ram: 2G
    disk: 16G
agents:
  {agent_name}:
    type: {agent_type}
    vm: agent
""",
        encoding="utf-8",
    )

    checked_binaries = []
    collected_binaries = []

    monkeypatch.setattr(status_module, "_load_multipass_entries", lambda: ({"agent": {"state": "Running"}}, None))
    monkeypatch.setattr(status_module, "_load_multipass_info_entries", lambda: ({}, None))
    monkeypatch.setattr(status_module, "_is_portforward_running", lambda: True)

    def fake_check(vm_name, binary):
        checked_binaries.append((vm_name, binary))
        return True

    def fake_collect(vm_name, binaries):
        collected_binaries.append((vm_name, list(binaries)))
        return [("8080", runtime_binary, "/home/ubuntu")]

    monkeypatch.setattr(status_module, "_check_agent_binary_installed", fake_check)
    monkeypatch.setattr(status_module, "_collect_running_agent_processes", fake_collect)

    runner = CliRunner()
    result = runner.invoke(status_command, ["--config", str(config_path)], env={"AGSEKIT_LANG": "en"})

    assert result.exit_code == 0
    assert checked_binaries == [("agent", runtime_binary)]
    assert collected_binaries == [("agent", [runtime_binary])]
    assert f"{agent_name} ({agent_type}): installed" in result.output
    assert f"PID 8080: {runtime_binary} (config name: {agent_name}), folder: /home/ubuntu" in result.output
