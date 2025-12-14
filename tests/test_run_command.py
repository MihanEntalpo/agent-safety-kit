from pathlib import Path
import sys
from typing import Dict

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.run as run_module
from agsekit_cli.commands.run import run_command


def _write_config(config_path: Path, source: Path) -> None:
    config_path.write_text(
        f"""
vms:
  agent:
    cpu: 1
    ram: 1G
    disk: 5G
mounts:
  - source: {source}
    target: /home/ubuntu/project
    vm: agent
    interval: 3
    backup: {source.parent / "backups"}
agents:
  qwen:
    type: qwen-code
    env:
      TOKEN: abc
    socks5_proxy: 10.0.0.2:1234
""",
        encoding="utf-8",
    )


def test_run_command_starts_backup_and_agent(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    calls: Dict[str, object] = {}

    def fake_run_in_vm(vm_name, workdir, command, env_vars):
        calls.update({
            "vm": vm_name,
            "workdir": workdir,
            "command": command,
            "env": env_vars,
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

    def fake_start_backup_process(mount, cli_path):
        backups.append((mount.source, mount.backup, cli_path))
        return DummyProcess()

    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", fake_start_backup_process)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", str(source), "--config", str(config_path), "--", "--flag"])

    assert result.exit_code == 0
    assert calls["vm"] == "agent"
    assert calls["workdir"] == Path("/home/ubuntu/project")
    assert calls["command"] == ["qwen-code", "--flag"]
    assert calls["env"]["TOKEN"] == "abc"
    assert calls["env"]["ALL_PROXY"].startswith("socks5://10.0.0.2:1234")
    assert backups and backups[0][0] == source.resolve()


def test_run_command_can_disable_backups(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    def fake_run_in_vm(vm_name, workdir, command, env_vars):
        return 0

    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)

    started = []

    def fake_start_backup_process(mount, cli_path):
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
