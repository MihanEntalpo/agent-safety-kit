import json
import sys
from pathlib import Path
from typing import Dict, Optional

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.install_agents as install_agents_module
from agsekit_cli.commands.install_agents import install_agents_command


def _write_config(
    config_path: Path,
    agents: list[tuple[str, str]],
    *,
    vm_proxychains: Optional[str] = None,
    agent_proxychains: Optional[Dict[str, str]] = None,
) -> None:
    vm_proxychains_line = f"    proxychains: {json.dumps(vm_proxychains)}\n" if vm_proxychains is not None else ""
    proxychains_by_agent = agent_proxychains or {}
    agent_entries = []
    for name, agent_type in agents:
        proxychains_line = ""
        if name in proxychains_by_agent:
            proxychains_line = f"    proxychains: {json.dumps(proxychains_by_agent[name])}\n"
        agent_entries.append(f"  {name}:\n    type: {agent_type}\n{proxychains_line}    env:\n      TOKEN: abc")
    joined_agent_entries = "\n".join(agent_entries)

    config_path.write_text(
        f"""
vms:
  agent:
    cpu: 1
    ram: 1G
    disk: 5G
{vm_proxychains_line if vm_proxychains_line else ''}agents:
{joined_agent_entries}
""",
        encoding="utf-8",
    )


def test_install_agents_defaults_to_single_agent(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("qwen", "qwen")])

    calls: list[tuple[str, str]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None) -> None:
        calls.append((vm.name, playbook_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = runner.invoke(install_agents_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls and calls[0][0] == "agent"
    assert calls[0][1] == "qwen.yml"
    assert calls[0][2] is None


def test_install_agents_requires_choice_when_multiple(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("qwen", "qwen"), ("codex", "codex")])

    runner = CliRunner()
    result = runner.invoke(install_agents_command, ["--config", str(config_path)])

    assert result.exit_code != 0
    assert "Provide an agent name" in result.output


def test_install_agents_passes_proxychains_override(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("qwen", "qwen")])

    calls: list[tuple[str, str, object]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None) -> None:
        calls.append((vm.name, playbook_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = runner.invoke(
        install_agents_command,
        ["--config", str(config_path), "--proxychains", "socks5://127.0.0.1:1080"],
    )

    assert result.exit_code == 0
    assert calls and calls[0][2] == "socks5://127.0.0.1:1080"


def test_install_agents_uses_agent_proxychains_override(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [("qwen", "qwen")],
        vm_proxychains="socks5://127.0.0.1:1080",
        agent_proxychains={"qwen": "http://10.0.0.5:3128"},
    )

    calls: list[tuple[str, str, object]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None) -> None:
        calls.append((vm.name, playbook_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = runner.invoke(
        install_agents_command,
        ["--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls and calls[0][2] == "http://10.0.0.5:3128"


def test_install_agents_agent_empty_proxychains_disables_vm_proxy(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [("qwen", "qwen")],
        vm_proxychains="socks5://127.0.0.1:1080",
        agent_proxychains={"qwen": ""},
    )

    calls: list[tuple[str, str, object]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None) -> None:
        calls.append((vm.name, playbook_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = runner.invoke(
        install_agents_command,
        ["--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls and calls[0][2] == ""
