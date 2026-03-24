import sys
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.restart_vm as restart_module
from agsekit_cli.commands.restart_vm import restart_vm_command


def _write_config(config_path: Path, vm_names: list[str]) -> None:
    entries = "\n".join(f"  {name}:\n    cpu: 1\n    ram: 1G\n    disk: 5G" for name in vm_names)
    config_path.write_text(f"vms:\n{entries}\n", encoding="utf-8")


def test_restart_single_vm(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    events: list[tuple[str, str]] = []

    monkeypatch.setattr(restart_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(restart_module, "_unmount_vm_mounts", lambda vm_name, mounts, debug=False: events.append(("unmount", vm_name)))
    monkeypatch.setattr(restart_module, "_stop_vm", lambda vm_name, debug=False: events.append(("stop", vm_name)))
    monkeypatch.setattr(restart_module, "_start_vm", lambda vm_name, debug=False: events.append(("start", vm_name)))

    runner = CliRunner()
    result = runner.invoke(restart_vm_command, ["agent", "--config", str(config_path)])

    assert result.exit_code == 0
    assert events == [("unmount", "agent"), ("stop", "agent"), ("start", "agent")]


def test_restart_defaults_to_single_vm(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    events: list[tuple[str, str]] = []

    monkeypatch.setattr(restart_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(restart_module, "_unmount_vm_mounts", lambda vm_name, mounts, debug=False: events.append(("unmount", vm_name)))
    monkeypatch.setattr(restart_module, "_stop_vm", lambda vm_name, debug=False: events.append(("stop", vm_name)))
    monkeypatch.setattr(restart_module, "_start_vm", lambda vm_name, debug=False: events.append(("start", vm_name)))

    runner = CliRunner()
    result = runner.invoke(restart_vm_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert events == [("unmount", "agent"), ("stop", "agent"), ("start", "agent")]


def test_restart_all_vms(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["vm1", "vm2"])

    events: list[tuple[str, str]] = []

    monkeypatch.setattr(restart_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(restart_module, "_unmount_vm_mounts", lambda vm_name, mounts, debug=False: events.append(("unmount", vm_name)))
    monkeypatch.setattr(restart_module, "_stop_vm", lambda vm_name, debug=False: events.append(("stop", vm_name)))
    monkeypatch.setattr(restart_module, "_start_vm", lambda vm_name, debug=False: events.append(("start", vm_name)))

    runner = CliRunner()
    result = runner.invoke(restart_vm_command, ["--all-vms", "--config", str(config_path)])

    assert result.exit_code == 0
    assert events == [
        ("unmount", "vm1"),
        ("stop", "vm1"),
        ("unmount", "vm2"),
        ("stop", "vm2"),
        ("start", "vm1"),
        ("start", "vm2"),
    ]


def test_restart_requires_vm_name_when_multiple(monkeypatch, tmp_path):
    monkeypatch.setenv("AGSEKIT_LANG", "ru")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["first", "second"])

    monkeypatch.setattr(restart_module, "ensure_multipass_available", lambda: None)

    runner = CliRunner()
    result = runner.invoke(restart_vm_command, ["--config", str(config_path)])

    assert result.exit_code != 0
    assert "Укажите имя ВМ" in result.output


def test_restart_vm_debug_output(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    monkeypatch.setattr(restart_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(restart_module, "_unmount_vm_mounts", lambda vm_name, mounts, debug=False: None)
    monkeypatch.setattr(restart_module, "_stop_vm", lambda vm_name, debug=False: None)
    monkeypatch.setattr(restart_module, "_start_vm", lambda vm_name, debug=False: None)

    runner = CliRunner()
    result = runner.invoke(
        restart_vm_command,
        ["agent", "--config", str(config_path), "--debug"],
        env={"AGSEKIT_LANG": "en"},
    )

    assert result.exit_code == 0
    assert "Stopping VM `agent`..." in result.output
    assert "Starting VM `agent`..." in result.output
    assert "VM `agent` restarted." in result.output
