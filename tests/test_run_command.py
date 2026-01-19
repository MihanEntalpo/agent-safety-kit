from pathlib import Path
import sys
from typing import Dict, Optional

import click
from click.testing import CliRunner
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.run as run_module
from agsekit_cli.commands.run import run_command


def _write_config(config_path: Path, source: Path, *, agent_type: str = "qwen", vm_proxychains: Optional[str] = None) -> None:
    proxychains_line = f"    proxychains: {vm_proxychains}\n" if vm_proxychains is not None else ""
    config_path.write_text(
        f"""
vms:
  agent:
    cpu: 1
    ram: 1G
    disk: 5G
{proxychains_line if proxychains_line else ''}mounts:
  - source: {source}
    target: /home/ubuntu/project
    vm: agent
    interval: 3
    backup: {source.parent / "backups"}
agents:
  qwen:
    type: {agent_type}
    env:
      TOKEN: abc
""",
        encoding="utf-8",
    )


def test_run_command_starts_backup_and_agent(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    calls: Dict[str, object] = {}

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        calls.update({
            "vm": vm_config.name,
            "workdir": workdir,
            "command": command,
            "env": env_vars,
            "proxychains": proxychains,
        })
        return 0

    class DummyProcess:
        def __init__(self):
            self.terminated = False
            self.killed = False

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.killed = True

    backups = []

    def fake_start_backup_process(mount, cli_path, skip_first=False, debug=False):
        backups.append((mount.source, mount.backup, cli_path, skip_first))
        return DummyProcess()

    one_off_calls = []

    def fake_backup_once(src, dst, show_progress=False, extra_excludes=None):
        one_off_calls.append((src, dst, show_progress))

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: False)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", fake_start_backup_process)
    monkeypatch.setattr(run_module, "backup_once", fake_backup_once)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", str(source), "--config", str(config_path), "--", "--flag"])

    assert result.exit_code == 0
    assert calls["vm"] == "agent"
    assert calls["workdir"] == Path("/home/ubuntu/project")
    assert calls["command"] == ["qwen", "--flag"]
    assert calls["env"]["TOKEN"] == "abc"
    assert "ALL_PROXY" not in calls["env"]
    assert one_off_calls == [(source.resolve(), (source.parent / "backups").resolve(), True)]
    assert backups and backups[0][0] == source.resolve()
    assert backups[0][3] is True
    assert calls["proxychains"] is None


def test_run_command_does_not_set_proxy_for_agent(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, agent_type="codex")

    calls: Dict[str, object] = {}

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        calls.update({
            "vm": vm_config.name,
            "workdir": workdir,
            "command": command,
            "env": env_vars,
            "proxychains": proxychains,
        })
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", str(source), "--config", str(config_path), "--", "--flag"])

    assert result.exit_code == 0
    assert "ALL_PROXY" not in calls["env"]
    assert calls["proxychains"] is None


def test_run_command_can_disable_backups(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    started = []

    def fake_start_backup_process(mount, cli_path, skip_first=False, debug=False):
        started.append("backup")
        return None

    monkeypatch.setattr(run_module, "start_backup_process", fake_start_backup_process)

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path), "--disable-backups"],
    )

    assert result.exit_code == 0
    assert not started


def test_run_command_prints_debug_commands(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    class DummyProcess:
        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        if debug:
            click.echo(f"[DEBUG] run_in_vm {vm_config.name} {workdir}")
        return 0

    def fake_start_backup_process(mount, cli_path, skip_first=False, debug=False):
        if debug:
            click.echo(f"[DEBUG] start_backup_process {mount.source} -> {mount.backup}")
        return DummyProcess()

    def fake_ensure_agent_binary_available(agent_command, vm_config, proxychains=None, debug=False):
        if debug:
            click.echo(f"[DEBUG] ensure_agent_binary_available {vm_config.name}")

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", fake_start_backup_process)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", fake_ensure_agent_binary_available)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path), "--debug", "--", "--flag"],
    )

    assert result.exit_code == 0


@pytest.mark.parametrize("relative_path, expected_suffix", [(".", Path(".")), ("./subdir/inner", Path("subdir/inner"))])
def test_run_command_resolves_relative_path_inside_mount(monkeypatch, tmp_path, relative_path, expected_suffix):
    source = tmp_path / "project"
    nested = source / "subdir" / "inner"
    nested.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    calls: Dict[str, object] = {}
    backups: Dict[str, object] = {}

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        calls.update({
            "vm": vm_config.name,
            "workdir": workdir,
        })
        return 0

    def fake_start_backup_process(mount, cli_path, skip_first=False, debug=False):
        backups.update({
            "source": mount.source,
            "backup": mount.backup,
        })
        return None

    monkeypatch.chdir(source)
    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", fake_start_backup_process)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", relative_path, "--config", str(config_path)],
    )

    assert result.exit_code == 0
    expected_workdir = Path("/home/ubuntu/project") / expected_suffix
    assert calls["workdir"] == expected_workdir
    assert backups["source"] == source.resolve()
    assert backups["backup"] == (source.parent / "backups").resolve()


def test_run_command_passes_proxychains_override(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, vm_proxychains="socks5://127.0.0.1:8080")

    calls: Dict[str, object] = {}
    checks: Dict[str, object] = {}

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        calls.update({
            "vm": vm_config.name,
            "workdir": workdir,
            "command": command,
            "env": env_vars,
            "proxychains": proxychains,
        })
        return 0

    def fake_ensure_agent_binary_available(agent_command, vm_config, proxychains=None, debug=False):
        checks["proxychains"] = proxychains

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", fake_ensure_agent_binary_available)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path), "--proxychains", "http://10.0.0.5:3128"],
    )

    assert result.exit_code == 0
    assert calls["proxychains"] == "http://10.0.0.5:3128"
    assert checks["proxychains"] == "http://10.0.0.5:3128"

    calls.clear()
    checks.clear()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path), "--proxychains", ""],
    )
    assert result.exit_code == 0
    assert calls["proxychains"] == ""
    assert checks["proxychains"] == ""
