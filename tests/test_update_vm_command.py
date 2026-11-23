from pathlib import Path
from typing import cast

import click
from click.testing import CliRunner

import agsekit_cli.commands.update_vm as update_module
from agsekit_cli.commands.update_vm import update_vm_command


def _invoke(runner: CliRunner, args: list[str]):
    return runner.invoke(cast(click.Command, update_vm_command), args)


def _config(path: Path, names: list[str]) -> None:
    entries = "\n".join(f"  {name}:\n    cpu: 2\n    ram: 2G\n    disk: 5G" for name in names)
    path.write_text(f"vms:\n{entries}\nagents: {{}}\n", encoding="utf-8")


def _patch_common(monkeypatch, state: str, changed: list[str]):
    monkeypatch.setattr(update_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(update_module, "fetch_existing_info", lambda: "info")
    monkeypatch.setattr(update_module, "get_vm_state", lambda *_: state)
    monkeypatch.setattr(update_module, "vm_mismatch_details", lambda *_: changed)
    monkeypatch.setattr(update_module, "_collect_running_configured_agents", lambda *_: [])


def test_update_stopped_vm_applies_cpu_and_memory(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    _config(config, ["agent"])
    calls = []
    _patch_common(monkeypatch, "stopped", ["cpus", "memory"])
    monkeypatch.setattr(update_module, "apply_vm_cpu_ram", lambda vm, _: calls.append(vm.name) or ["cpus", "memory"])

    result = _invoke(CliRunner(), ["agent", "--config", str(config)])

    assert result.exit_code == 0
    assert calls == ["agent"]
    assert "Updated VM agent: cpus, memory." in result.output


def test_update_running_vm_requires_force_when_non_interactive(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    _config(config, ["agent"])
    _patch_common(monkeypatch, "running", ["cpus"])

    result = _invoke(CliRunner(), ["agent", "--non-interactive", "--config", str(config)])

    assert result.exit_code != 0
    assert "Re-run with --force" in result.output


def test_update_running_vm_force_stops_updates_and_starts(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    _config(config, ["agent"])
    calls = []
    _patch_common(monkeypatch, "running", ["memory"])
    monkeypatch.setattr(update_module, "_stop_vm_for_resize", lambda name: calls.append(("stop", name)))
    monkeypatch.setattr(update_module, "apply_vm_cpu_ram", lambda vm, _: calls.append(("set", vm.name)) or ["memory"])
    monkeypatch.setattr(update_module, "_start_vm_after_resize", lambda name: calls.append(("start", name)))

    result = _invoke(CliRunner(), ["agent", "--force", "--config", str(config)])

    assert result.exit_code == 0
    assert calls == [("stop", "agent"), ("set", "agent"), ("start", "agent")]


def test_update_reports_running_agents_before_forced_restart(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    _config(config, ["agent"])
    reported = []
    _patch_common(monkeypatch, "running", ["cpus"])
    monkeypatch.setattr(
        update_module,
        "_collect_running_configured_agents",
        lambda *_: [("agent", "codex", "codex", "/workspace")],
    )
    monkeypatch.setattr(update_module, "_report_running_agents", lambda agents: reported.extend(agents))
    monkeypatch.setattr(update_module, "_stop_vm_for_resize", lambda _: None)
    monkeypatch.setattr(update_module, "apply_vm_cpu_ram", lambda *_: ["cpus"])
    monkeypatch.setattr(update_module, "_start_vm_after_resize", lambda _: None)

    result = _invoke(CliRunner(), ["agent", "--force", "--config", str(config)])

    assert result.exit_code == 0
    assert reported == [("agent", "codex", "codex", "/workspace")]


def test_update_skips_suspended_vm(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    _config(config, ["agent"])
    _patch_common(monkeypatch, "suspended", ["cpus"])

    result = _invoke(CliRunner(), ["agent", "--config", str(config)])

    assert result.exit_code == 0
    assert "suspended" in result.output


def test_update_all_continues_after_absent_vm(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    _config(config, ["absent", "stopped"])
    calls = []
    monkeypatch.setattr(update_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(update_module, "fetch_existing_info", lambda: "info")
    monkeypatch.setattr(update_module, "get_vm_state", lambda _, name: None if name == "absent" else "stopped")
    monkeypatch.setattr(update_module, "vm_mismatch_details", lambda *_: ["cpus"])
    monkeypatch.setattr(update_module, "apply_vm_cpu_ram", lambda vm, _: calls.append(vm.name) or ["cpus"])

    result = _invoke(CliRunner(), ["--all-vms", "--config", str(config)])

    assert result.exit_code == 0
    assert calls == ["stopped"]
    assert "does not exist" in result.output
