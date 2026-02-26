import sys
from pathlib import Path

import yaml
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.addmount as addmount_commands


def _write_config(path: Path, *, agents: list[str]) -> None:
    agents_yaml = "\n".join([f"  {name}:\n    type: {name}" for name in agents])
    path.write_text(
        f"""
vms:
  agent:
    cpu: 1
    ram: 1G
    disk: 5G
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
