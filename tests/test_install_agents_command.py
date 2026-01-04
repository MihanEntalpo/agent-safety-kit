import sys
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.install_agents as install_agents_module
from agsekit_cli.commands.install_agents import install_agents_command


def _write_config(config_path: Path, agents: list[tuple[str, str]]) -> None:
    agent_entries = "\n".join(
        f"  {name}:\n    type: {agent_type}\n    env:\n      TOKEN: abc" for name, agent_type in agents
    )
    config_path.write_text(
        f"""
vms:
  agent:
    cpu: 1
    ram: 1G
    disk: 5G
agents:
{agent_entries}
""",
        encoding="utf-8",
    )


def test_install_agents_defaults_to_single_agent(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("qwen", "qwen")])

    calls: list[tuple[str, str]] = []

    def fake_run_install_script(vm, script_path: Path, proxychains=None) -> None:
        calls.append((vm.name, script_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_script", fake_run_install_script)

    runner = CliRunner()
    result = runner.invoke(install_agents_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls and calls[0][0] == "agent"
    assert calls[0][1] == "qwen.sh"
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

    def fake_run_install_script(vm, script_path: Path, proxychains=None) -> None:
        calls.append((vm.name, script_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_script", fake_run_install_script)

    runner = CliRunner()
    result = runner.invoke(
        install_agents_command,
        ["--config", str(config_path), "--proxychains", "socks5://127.0.0.1:1080"],
    )

    assert result.exit_code == 0
    assert calls and calls[0][2] == "socks5://127.0.0.1:1080"
