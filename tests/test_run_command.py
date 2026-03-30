import json
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
from agsekit_cli.config import AGENT_RUNTIME_BINARIES
from agsekit_cli.commands.run import run_command
from agsekit_cli.mounts import normalize_path

_REAL_ENSURE_MOUNT_REGISTERED_FOR_RUN = run_module._ensure_mount_registered_for_run


@pytest.fixture(autouse=True)
def bypass_mount_registration_prompt(monkeypatch):
    monkeypatch.setattr(run_module, "_ensure_mount_registered_for_run", lambda *args, **kwargs: True)


def _write_config(
    config_path: Path,
    source: Path,
    *,
    agent_type: str = "qwen",
    vm_proxychains: Optional[str] = None,
    vm_allowed_agents: Optional[list[str]] = None,
    agent_proxychains: Optional[str] = None,
    agent_proxychains_set: bool = False,
    mount_allowed_agents: Optional[list[str]] = None,
    include_codex_agent: bool = False,
    create_source: bool = True,
) -> None:
    if create_source:
        source.mkdir(parents=True, exist_ok=True)
    proxychains_line = f"    proxychains: {json.dumps(vm_proxychains)}\n" if vm_proxychains is not None else ""
    vm_allowed_agents_line = (
        f"    allowed_agents: {json.dumps(vm_allowed_agents)}\n"
        if vm_allowed_agents is not None
        else ""
    )
    agent_proxychains_line = ""
    if agent_proxychains_set:
        value = "" if agent_proxychains is None else agent_proxychains
        agent_proxychains_line = f"    proxychains: {json.dumps(value)}\n"
    allowed_agents_line = (
        f"    allowed_agents: {json.dumps(mount_allowed_agents)}\n"
        if mount_allowed_agents is not None
        else ""
    )
    codex_agent_block = ""
    if include_codex_agent:
        codex_agent_block = """
  codex:
    type: codex
    vm: agent
    env: {}
"""
    config_path.write_text(
        f"""
vms:
  agent:
    cpu: 1
    ram: 1G
    disk: 5G
{proxychains_line if proxychains_line else ''}{vm_allowed_agents_line if vm_allowed_agents_line else ''}mounts:
  - source: {source}
    target: /home/ubuntu/project
    vm: agent
{allowed_agents_line if allowed_agents_line else ''}    interval: 3
    backup: {source.parent / "backups"}
agents:
  qwen:
    type: {agent_type}
{agent_proxychains_line if agent_proxychains_line else ''}    vm: agent
    env:
      TOKEN: abc
{codex_agent_block if codex_agent_block else ''}
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


def test_run_command_for_forgecode_forces_tracker_env(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, agent_type="forgecode")

    calls: Dict[str, object] = {}

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        calls.update({
            "command": command,
            "env": env_vars,
        })
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", str(source), "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls["command"] == ["forge"]
    assert calls["env"] == {
        "TOKEN": "abc",
        "FORGE_TRACKER": "false",
    }


def test_run_command_reports_missing_source_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("AGSEKIT_LANG", "en")
    source = tmp_path / "missing"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, create_source=False)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", str(source), "--config", str(config_path)])

    assert result.exit_code != 0
    assert str(normalize_path(source)) in result.output
    assert "does not exist" in result.output


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


def test_run_command_uses_current_directory_mount_when_source_not_passed(monkeypatch, tmp_path):
    source = tmp_path / "project"
    nested = source / "subdir" / "inner"
    nested.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    calls: Dict[str, object] = {}
    backups: Dict[str, object] = {}

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        calls["workdir"] = workdir
        return 0

    def fake_start_backup_process(mount, cli_path, skip_first=False, debug=False):
        backups["source"] = mount.source
        return None

    monkeypatch.chdir(nested)
    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", fake_start_backup_process)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls["workdir"] == Path("/home/ubuntu/project/subdir/inner")
    assert backups["source"] == source.resolve()


def test_run_command_warns_when_mounted_directory_is_empty_inside_vm(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "main.py").write_text("print('hi')", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)
    monkeypatch.setattr(
        run_module,
        "load_multipass_mounts",
        lambda **_kwargs: {"agent": {(source.resolve(), Path("/home/ubuntu/project"))}},
    )
    monkeypatch.setattr(run_module, "vm_path_has_entries", lambda *_args, **_kwargs: False)

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path)],
        env={"AGSEKIT_LANG": "ru"},
        input="y\n",
    )

    assert result.exit_code == 0
    assert (
        f"WARNING: Папка {source.resolve()} примонтирована, но внутри ВМ в ней пусто, воспользуйтесь командой agsekit doctor"
        in result.output
    )
    assert "Всё равно запустить агента? [y/N]: y" in result.output


def test_run_command_warns_and_confirms_for_current_directory(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "main.py").write_text("print('hi')", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, include_codex_agent=True)

    calls: Dict[str, object] = {}

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        calls["workdir"] = workdir
        calls["command"] = command
        return 0

    monkeypatch.chdir(source)
    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)
    monkeypatch.setattr(
        run_module,
        "load_multipass_mounts",
        lambda **_kwargs: {"agent": {(source.resolve(), Path("/home/ubuntu/project"))}},
    )
    monkeypatch.setattr(run_module, "vm_path_has_entries", lambda *_args, **_kwargs: False)

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["codex", ".", "--config", str(config_path)],
        env={"AGSEKIT_LANG": "ru"},
        input="y\n",
    )

    assert result.exit_code == 0
    assert (
        f"WARNING: Папка {source.resolve()} примонтирована, но внутри ВМ в ней пусто, воспользуйтесь командой agsekit doctor"
        in result.output
    )
    assert "Всё равно запустить агента? [y/N]: y" in result.output
    assert calls["workdir"] == Path("/home/ubuntu/project")
    assert calls["command"] == ["codex"]


def test_run_command_aborts_when_empty_vm_directory_warning_is_rejected(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "main.py").write_text("print('hi')", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    run_calls: list[str] = []

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        run_calls.append("run")
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)
    monkeypatch.setattr(
        run_module,
        "load_multipass_mounts",
        lambda **_kwargs: {"agent": {(source.resolve(), Path("/home/ubuntu/project"))}},
    )
    monkeypatch.setattr(run_module, "vm_path_has_entries", lambda *_args, **_kwargs: False)

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path)],
        env={"AGSEKIT_LANG": "ru"},
        input="\n",
    )

    assert result.exit_code != 0
    assert "Всё равно запустить агента? [y/N]:" in result.output
    assert not run_calls


def test_run_command_does_not_warn_for_unmounted_directory(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "main.py").write_text("print('hi')", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "load_multipass_mounts", lambda **_kwargs: {"agent": set()})

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path)],
        env={"AGSEKIT_LANG": "ru"},
    )

    assert result.exit_code == 0
    assert "WARNING: Папка" not in result.output


def test_run_command_prompts_to_mount_unmounted_directory_and_continues(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "main.py").write_text("print('hi')", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    run_calls: list[Path] = []
    mount_calls: list[Path] = []

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        run_calls.append(workdir)
        return 0

    monkeypatch.setattr(run_module, "_ensure_mount_registered_for_run", _REAL_ENSURE_MOUNT_REGISTERED_FOR_RUN)
    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "load_multipass_mounts", lambda **_kwargs: {"agent": set()})
    monkeypatch.setattr(run_module, "mount_directory", lambda mount: mount_calls.append(mount.source))

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path)],
        env={"AGSEKIT_LANG": "ru"},
        input="y\n",
    )

    assert result.exit_code == 0
    assert f"Папка {source.resolve()} сейчас не примонтирована. Примонтировать? [Y/n]: y" in result.output
    assert f"Смонтировано {source.resolve()} в agent:/home/ubuntu/project." in result.output
    assert mount_calls == [source.resolve()]
    assert run_calls == [Path("/home/ubuntu/project")]


def test_run_command_stops_when_mount_prompt_is_rejected(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "main.py").write_text("print('hi')", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    run_calls: list[str] = []
    mount_calls: list[str] = []

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        run_calls.append("run")
        return 0

    monkeypatch.setattr(run_module, "_ensure_mount_registered_for_run", _REAL_ENSURE_MOUNT_REGISTERED_FOR_RUN)
    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "load_multipass_mounts", lambda **_kwargs: {"agent": set()})
    monkeypatch.setattr(run_module, "mount_directory", lambda mount: mount_calls.append("mount"))

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path)],
        env={"AGSEKIT_LANG": "ru"},
        input="n\n",
    )

    assert result.exit_code == 0
    assert f"Папка {source.resolve()} сейчас не примонтирована. Примонтировать? [Y/n]: n" in result.output
    assert not mount_calls
    assert not run_calls


def test_run_command_requires_mounted_directory_in_non_interactive_mode(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "main.py").write_text("print('hi')", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    run_calls: list[str] = []

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        run_calls.append("run")
        return 0

    monkeypatch.setattr(run_module, "_ensure_mount_registered_for_run", _REAL_ENSURE_MOUNT_REGISTERED_FOR_RUN)
    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "load_multipass_mounts", lambda **_kwargs: {"agent": set()})

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path), "--non-interactive"],
        env={"AGSEKIT_LANG": "ru"},
    )

    assert result.exit_code != 0
    assert "но сейчас не примонтирована в Multipass" in result.output
    assert not run_calls


def test_run_command_auto_mounts_without_prompt_in_interactive_mode(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "main.py").write_text("print('hi')", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    run_calls: list[Path] = []
    mount_calls: list[Path] = []

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        run_calls.append(workdir)
        return 0

    monkeypatch.setattr(run_module, "_ensure_mount_registered_for_run", _REAL_ENSURE_MOUNT_REGISTERED_FOR_RUN)
    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "load_multipass_mounts", lambda **_kwargs: {"agent": set()})
    monkeypatch.setattr(run_module, "mount_directory", lambda mount: mount_calls.append(mount.source))

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path), "--auto-mount"],
        env={"AGSEKIT_LANG": "ru"},
    )

    assert result.exit_code == 0
    assert "сейчас не примонтирована. Примонтировать?" not in result.output
    assert f"Смонтировано {source.resolve()} в agent:/home/ubuntu/project." in result.output
    assert mount_calls == [source.resolve()]
    assert run_calls == [Path("/home/ubuntu/project")]


def test_run_command_auto_mounts_in_non_interactive_mode(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "main.py").write_text("print('hi')", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    run_calls: list[Path] = []
    mount_calls: list[Path] = []

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        run_calls.append(workdir)
        return 0

    monkeypatch.setattr(run_module, "_ensure_mount_registered_for_run", _REAL_ENSURE_MOUNT_REGISTERED_FOR_RUN)
    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "load_multipass_mounts", lambda **_kwargs: {"agent": set()})
    monkeypatch.setattr(run_module, "mount_directory", lambda mount: mount_calls.append(mount.source))

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path), "--non-interactive", "--auto-mount"],
        env={"AGSEKIT_LANG": "ru"},
    )

    assert result.exit_code == 0
    assert "сейчас не примонтирована. Примонтировать?" not in result.output
    assert f"Смонтировано {source.resolve()} в agent:/home/ubuntu/project." in result.output
    assert mount_calls == [source.resolve()]
    assert run_calls == [Path("/home/ubuntu/project")]


def test_run_command_does_not_warn_for_empty_host_directory(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)
    monkeypatch.setattr(
        run_module,
        "load_multipass_mounts",
        lambda **_kwargs: {"agent": {(source.resolve(), Path("/home/ubuntu/project"))}},
    )
    vm_checks: list[str] = []
    monkeypatch.setattr(
        run_module,
        "vm_path_has_entries",
        lambda *_args, **_kwargs: vm_checks.append("checked") or False,
    )

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path)],
        env={"AGSEKIT_LANG": "ru"},
    )

    assert result.exit_code == 0
    assert "WARNING: Папка" not in result.output
    assert not vm_checks


def test_run_command_without_source_keeps_default_workdir_when_cwd_not_in_mount(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source)

    calls: Dict[str, object] = {}
    started = {"backup": False}

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        calls["workdir"] = workdir
        return 0

    def fake_start_backup_process(*_args, **_kwargs):
        started["backup"] = True
        return None

    monkeypatch.chdir(outside_dir)
    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", fake_start_backup_process)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls["workdir"] == run_module.DEFAULT_WORKDIR
    assert started["backup"] is False


def test_run_command_passes_proxychains_override(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        source,
        vm_proxychains="socks5://127.0.0.1:8080",
        agent_proxychains="http://192.168.1.1:3128",
        agent_proxychains_set=True,
    )

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


def test_run_command_uses_agent_proxychains_override(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        source,
        vm_proxychains="socks5://127.0.0.1:8080",
        agent_proxychains="http://192.168.1.1:3128",
        agent_proxychains_set=True,
    )

    calls: Dict[str, object] = {}
    checks: Dict[str, object] = {}

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        calls["proxychains"] = proxychains
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
        ["qwen", str(source), "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls["proxychains"] == "http://192.168.1.1:3128"
    assert checks["proxychains"] == "http://192.168.1.1:3128"


@pytest.mark.parametrize(("agent_type", "runtime_binary"), sorted(AGENT_RUNTIME_BINARIES.items()))
def test_run_command_uses_runtime_binary(monkeypatch, tmp_path, agent_type: str, runtime_binary: str):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        source,
        agent_type=agent_type,
        vm_proxychains="socks5://127.0.0.1:8080",
    )

    calls: Dict[str, object] = {}
    checks: Dict[str, object] = {}

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        calls["proxychains"] = proxychains
        calls["command"] = list(command)
        return 0

    def fake_ensure_agent_binary_available(agent_command, vm_config, proxychains=None, debug=False):
        checks["proxychains"] = proxychains
        checks["command"] = list(agent_command)

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", fake_ensure_agent_binary_available)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(
        run_command,
        ["qwen", str(source), "--config", str(config_path), "--", "--print"],
    )

    assert result.exit_code == 0
    assert calls["proxychains"] is None
    assert checks["proxychains"] is None
    assert calls["command"][0] == runtime_binary
    assert checks["command"][0] == runtime_binary


def test_run_command_agent_empty_proxychains_disables_vm_proxy(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        source,
        vm_proxychains="socks5://127.0.0.1:8080",
        agent_proxychains="",
        agent_proxychains_set=True,
    )

    calls: Dict[str, object] = {}
    checks: Dict[str, object] = {}

    def fake_run_in_vm(vm_config, workdir, command, env_vars, proxychains=None, debug=False):
        calls["proxychains"] = proxychains
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
        ["qwen", str(source), "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls["proxychains"] == ""
    assert checks["proxychains"] == ""


def test_run_command_rejects_agent_outside_mount_allowed_agents(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, mount_allowed_agents=["codex"])

    called = {"run_in_vm": False}

    def fake_run_in_vm(*_args, **_kwargs):
        called["run_in_vm"] = True
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", str(source), "--config", str(config_path)])

    assert result.exit_code != 0
    assert "allowed_agents" in result.output
    assert called["run_in_vm"] is False


def test_run_command_allows_agent_from_mount_allowed_agents(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, mount_allowed_agents=["qwen"])

    called = {"run_in_vm": False}

    def fake_run_in_vm(*_args, **_kwargs):
        called["run_in_vm"] = True
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", str(source), "--config", str(config_path)])

    assert result.exit_code == 0
    assert called["run_in_vm"] is True


def test_run_command_rejects_agent_in_mount_subdirectory_when_not_allowed(monkeypatch, tmp_path):
    source = tmp_path / "project"
    nested = source / "nested" / "inner"
    nested.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, mount_allowed_agents=["codex"])

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", str(nested), "--config", str(config_path)])

    assert result.exit_code != 0
    assert "allowed_agents" in result.output


def test_run_command_without_source_rejects_disallowed_agent_in_current_directory_mount(monkeypatch, tmp_path):
    source = tmp_path / "project"
    nested = source / "nested" / "inner"
    nested.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, mount_allowed_agents=["codex"])

    called = {"run_in_vm": False}

    def fake_run_in_vm(*_args, **_kwargs):
        called["run_in_vm"] = True
        return 0

    monkeypatch.chdir(nested)
    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", "--config", str(config_path)])

    assert result.exit_code != 0
    assert "allowed_agents" in result.output
    assert called["run_in_vm"] is False


def test_run_command_rejects_agent_outside_vm_allowed_agents(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, vm_allowed_agents=["codex"])

    called = {"run_in_vm": False}

    def fake_run_in_vm(*_args, **_kwargs):
        called["run_in_vm"] = True
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", str(source), "--config", str(config_path)])

    assert result.exit_code != 0
    assert "allowed_agents" in result.output
    assert "`agent`" in result.output
    assert called["run_in_vm"] is False


def test_run_command_allows_agent_from_vm_allowed_agents(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, vm_allowed_agents=["qwen"])

    called = {"run_in_vm": False}

    def fake_run_in_vm(*_args, **_kwargs):
        called["run_in_vm"] = True
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", str(source), "--config", str(config_path)])

    assert result.exit_code == 0
    assert called["run_in_vm"] is True


def test_run_command_prefers_mount_allowed_agents_over_vm_allowed_agents(monkeypatch, tmp_path):
    source = tmp_path / "project"
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        source,
        vm_allowed_agents=["codex"],
        mount_allowed_agents=["qwen"],
        include_codex_agent=True,
    )

    called = {"run_in_vm": False}

    def fake_run_in_vm(*_args, **_kwargs):
        called["run_in_vm"] = True
        return 0

    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", str(source), "--config", str(config_path)])

    assert result.exit_code == 0
    assert called["run_in_vm"] is True


def test_run_command_without_mount_uses_vm_allowed_agents(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source, vm_allowed_agents=["codex"])

    called = {"run_in_vm": False}

    def fake_run_in_vm(*_args, **_kwargs):
        called["run_in_vm"] = True
        return 0

    monkeypatch.chdir(outside_dir)
    monkeypatch.setattr(run_module, "_has_existing_backup", lambda *_: True)
    monkeypatch.setattr(run_module, "run_in_vm", fake_run_in_vm)
    monkeypatch.setattr(run_module, "start_backup_process", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "ensure_agent_binary_available", lambda *_, **__: None)
    monkeypatch.setattr(run_module, "backup_once", lambda *_, **__: None)

    runner = CliRunner()
    result = runner.invoke(run_command, ["qwen", "--config", str(config_path)])

    assert result.exit_code != 0
    assert "allowed_agents" in result.output
    assert "`agent`" in result.output
    assert called["run_in_vm"] is False


def test_run_command_reports_context_for_agent_type_field_typo(tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    config_path = tmp_path / "config.yaml"
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
agents:
  cline:
    tpye: cline
    vm: agent
    env: {{}}
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(run_command, ["cline", str(source), "--config", str(config_path)])

    assert result.exit_code != 0
    assert f"Configuration error in file `{config_path}`" in result.output
    assert "path agents.cline" in result.output
    assert "Agent `cline`" in result.output
    assert "looks like a typo" in result.output
    assert "`tpye`" in result.output


def test_run_command_suggests_agent_type_for_typo(tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    config_path = tmp_path / "config.yaml"
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
agents:
  cline:
    type: cilne
    vm: agent
    env: {{}}
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(run_command, ["cline", str(source), "--config", str(config_path)])

    assert result.exit_code != 0
    assert f"Configuration error in file `{config_path}`" in result.output
    assert "path agents.cline" in result.output
    assert "Agent `cline`" in result.output
    assert "Unknown agent type: cilne." in result.output
    assert "Did you mean `cline`?" in result.output
