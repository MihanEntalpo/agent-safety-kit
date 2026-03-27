import sys
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.down as down_module
from agsekit_cli.commands.down import down_command


def _write_config(config_path: Path, vm_names: list[str]) -> None:
    entries = "\n".join(f"  {name}:\n    cpu: 1\n    ram: 1G\n    disk: 5G" for name in vm_names)
    config_path.write_text(f"vms:\n{entries}\n", encoding="utf-8")


def test_down_stops_all_vms_when_no_agents_running(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["vm1", "vm2"])

    shutdown_calls = []
    systemd_calls = []

    monkeypatch.setattr(down_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(down_module, "_collect_running_configured_agents", lambda vm_names, agents: [])
    monkeypatch.setattr(down_module, "stop_portforward_service", lambda announce=False: systemd_calls.append(announce))
    monkeypatch.setattr(
        down_module,
        "_shutdown_vms",
        lambda targets, mounts, *, debug: shutdown_calls.append((list(targets), mounts, debug)),
    )

    runner = CliRunner()
    result = runner.invoke(down_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert systemd_calls == [False]
    assert shutdown_calls == [(["vm1", "vm2"], [], False)]


def test_down_requires_confirmation_in_non_interactive_when_agents_running(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent-vm"])

    monkeypatch.setattr(down_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        down_module,
        "_collect_running_configured_agents",
        lambda vm_names, agents: [("agent-vm", "codex", "codex-glibc-prebuilt", "/work/project")],
    )
    monkeypatch.setattr(down_module, "is_interactive_terminal", lambda: False)

    runner = CliRunner()
    result = runner.invoke(down_command, ["--config", str(config_path), "--non-interactive"])

    assert result.exit_code != 0
    assert "Configured running agents were detected" in result.output
    assert "agent-vm" in result.output
    assert "/work/project" in result.output


def test_down_cancels_when_user_rejects_confirmation(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent-vm"])

    shutdown_calls = []
    systemd_calls = []

    monkeypatch.setattr(down_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        down_module,
        "_collect_running_configured_agents",
        lambda vm_names, agents: [("agent-vm", "codex", "codex-glibc-prebuilt", "/work/project")],
    )
    monkeypatch.setattr(down_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(down_module.click, "confirm", lambda text, default=False: False)
    monkeypatch.setattr(down_module, "stop_portforward_service", lambda announce=False: systemd_calls.append(announce))
    monkeypatch.setattr(
        down_module,
        "_shutdown_vms",
        lambda targets, mounts, *, debug: shutdown_calls.append((list(targets), mounts, debug)),
    )

    runner = CliRunner()
    result = runner.invoke(down_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert "Shutdown cancelled." in result.output
    assert systemd_calls == []
    assert shutdown_calls == []


def test_down_force_skips_confirmation(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent-vm"])

    shutdown_calls = []
    systemd_calls = []

    monkeypatch.setattr(down_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        down_module,
        "_collect_running_configured_agents",
        lambda vm_names, agents: [("agent-vm", "codex", "codex-glibc-prebuilt", "/work/project")],
    )
    monkeypatch.setattr(down_module, "stop_portforward_service", lambda announce=False: systemd_calls.append(announce))
    monkeypatch.setattr(
        down_module,
        "_shutdown_vms",
        lambda targets, mounts, *, debug: shutdown_calls.append((list(targets), mounts, debug)),
    )

    runner = CliRunner()
    result = runner.invoke(down_command, ["--config", str(config_path), "--force"])

    assert result.exit_code == 0
    assert systemd_calls == [False]
    assert shutdown_calls == [(["agent-vm"], [], False)]
