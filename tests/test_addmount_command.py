import sys
from pathlib import Path
from typing import Optional

import yaml
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.addmount as addmount_commands


def _write_config(path: Path, *, agents: list[str], vms: Optional[list[str]] = None) -> None:
    vm_names = vms or ["agent"]
    vms_yaml = "\n".join([f"  {name}:\n    cpu: 1\n    ram: 1G\n    disk: 5G" for name in vm_names])
    agents_yaml = "\n".join([f"  {name}:\n    type: {name}" for name in agents])
    path.write_text(
        f"""
vms:
{vms_yaml}
agents:
{agents_yaml}
""",
        encoding="utf-8",
    )


def _read_mount_entry(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    mounts = payload.get("mounts") or []
    assert len(mounts) == 1
    return mounts[0]


def test_addmount_accepts_allowed_agents_option(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "backup"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, agents=["qwen", "codex", "claude"])

    runner = CliRunner()
    result = runner.invoke(
        addmount_commands.addmount_command,
        [
            str(source),
            str(target),
            str(backup),
            "7",
            "--allowed-agents",
            "qwen,codex",
            "--config",
            str(config_path),
            "-y",
        ],
    )

    assert result.exit_code == 0
    mount_entry = _read_mount_entry(config_path)
    assert mount_entry["allowed_agents"] == ["qwen", "codex"]
    assert mount_entry["vm"] == "agent"


def test_addmount_accepts_vm_option(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "backup"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, agents=["qwen"], vms=["primary", "secondary"])

    runner = CliRunner()
    result = runner.invoke(
        addmount_commands.addmount_command,
        [
            str(source),
            str(target),
            str(backup),
            "5",
            "--vm",
            "secondary",
            "--allowed-agents",
            "qwen",
            "--config",
            str(config_path),
            "-y",
        ],
    )

    assert result.exit_code == 0
    mount_entry = _read_mount_entry(config_path)
    assert mount_entry["vm"] == "secondary"


def test_addmount_uses_single_vm_by_default(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "backup"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, agents=["qwen"], vms=["single-vm"])

    runner = CliRunner()
    result = runner.invoke(
        addmount_commands.addmount_command,
        [
            str(source),
            str(target),
            str(backup),
            "5",
            "--allowed-agents",
            "qwen",
            "--config",
            str(config_path),
            "-y",
        ],
    )

    assert result.exit_code == 0
    mount_entry = _read_mount_entry(config_path)
    assert mount_entry["vm"] == "single-vm"


def test_addmount_mount_now_prompt_defaults_to_yes(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "backup"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, agents=["qwen"])

    mount_calls: list[Path] = []
    monkeypatch.setattr(addmount_commands, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(addmount_commands, "mount_directory", lambda mount: mount_calls.append(mount.source))

    runner = CliRunner()
    result = runner.invoke(
        addmount_commands.addmount_command,
        [
            str(source),
            str(target),
            str(backup),
            "5",
            "--max-backups",
            "100",
            "--backup-clean-method",
            "thin",
            "--allowed-agents",
            "qwen",
            "--config",
            str(config_path),
            "-y",
        ],
        env={"AGSEKIT_LANG": "ru"},
        input="\n",
    )

    assert result.exit_code == 0
    assert "Сразу примонтировать папку? [Y/n]:" in result.output
    assert mount_calls == [source.resolve()]


def test_addmount_interactive_prompts_for_vm_when_multiple(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "backup"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, agents=["qwen"], vms=["primary", "secondary"])

    monkeypatch.setattr(addmount_commands, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(addmount_commands.click, "prompt", lambda *_args, **_kwargs: "secondary")
    monkeypatch.setattr(addmount_commands.click, "confirm", lambda *_args, **_kwargs: False)

    runner = CliRunner()
    result = runner.invoke(
        addmount_commands.addmount_command,
        [
            str(source),
            str(target),
            str(backup),
            "5",
            "--max-backups",
            "100",
            "--backup-clean-method",
            "thin",
            "--allowed-agents",
            "qwen",
            "--config",
            str(config_path),
            "-y",
        ],
    )

    assert result.exit_code == 0
    mount_entry = _read_mount_entry(config_path)
    assert mount_entry["vm"] == "secondary"


def test_addmount_rejects_unknown_vm(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "backup"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, agents=["qwen"], vms=["primary"])

    runner = CliRunner()
    result = runner.invoke(
        addmount_commands.addmount_command,
        [
            str(source),
            str(target),
            str(backup),
            "5",
            "--vm",
            "missing",
            "--allowed-agents",
            "qwen",
            "--config",
            str(config_path),
            "-y",
        ],
    )

    assert result.exit_code != 0
    assert "missing" in result.output


def test_addmount_rejects_unknown_allowed_agents(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "backup"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, agents=["qwen"])

    runner = CliRunner()
    result = runner.invoke(
        addmount_commands.addmount_command,
        [
            str(source),
            str(target),
            str(backup),
            "5",
            "--allowed-agents",
            "qwen,codex",
            "--config",
            str(config_path),
            "-y",
        ],
    )

    assert result.exit_code != 0
    assert "Unknown agent" in result.output


def test_addmount_interactive_can_skip_allowed_agents(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "backup"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, agents=["qwen", "codex", "claude"])

    monkeypatch.setattr(addmount_commands, "is_interactive_terminal", lambda: True)
    answers = iter([False, False])
    monkeypatch.setattr(addmount_commands.click, "confirm", lambda *_args, **_kwargs: next(answers))

    runner = CliRunner()
    result = runner.invoke(
        addmount_commands.addmount_command,
        [
            str(source),
            str(target),
            str(backup),
            "5",
            "--max-backups",
            "100",
            "--backup-clean-method",
            "thin",
            "--config",
            str(config_path),
            "-y",
        ],
    )

    assert result.exit_code == 0
    mount_entry = _read_mount_entry(config_path)
    assert "allowed_agents" not in mount_entry


def test_addmount_interactive_selects_allowed_agents(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "backup"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, agents=["qwen", "codex", "claude"])

    monkeypatch.setattr(addmount_commands, "is_interactive_terminal", lambda: True)
    answers = iter([True, True, False, True, False])
    monkeypatch.setattr(addmount_commands.click, "confirm", lambda *_args, **_kwargs: next(answers))

    runner = CliRunner()
    result = runner.invoke(
        addmount_commands.addmount_command,
        [
            str(source),
            str(target),
            str(backup),
            "5",
            "--max-backups",
            "100",
            "--backup-clean-method",
            "thin",
            "--config",
            str(config_path),
            "-y",
        ],
    )

    assert result.exit_code == 0
    mount_entry = _read_mount_entry(config_path)
    assert mount_entry["allowed_agents"] == ["qwen", "claude"]
