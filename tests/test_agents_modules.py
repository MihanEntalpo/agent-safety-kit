from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agsekit_cli.agents_modules import AGENT_RUNTIME_BINARIES, SUPPORTED_AGENT_TYPES, build_agent_module, get_agent_class
from agsekit_cli.config import AgentConfig


def test_supported_agent_types_match_runtime_mapping():
    assert tuple(AGENT_RUNTIME_BINARIES.keys()) == SUPPORTED_AGENT_TYPES


def test_build_agent_module_returns_specific_agent_class():
    agent = AgentConfig(name="main", type="codeforge", env={}, vm_name=None)

    module = build_agent_module(agent)

    assert module.__class__.__name__ == "CodeforgeAgent"


def test_codeforge_agent_forces_tracker_in_env():
    agent = AgentConfig(
        name="main",
        type="codeforge",
        env={"TOKEN": "abc", "FORGE_TRACKER": "true"},
        vm_name=None,
    )

    module = build_agent_module(agent)

    assert module.build_env() == {
        "TOKEN": "abc",
        "FORGE_TRACKER": "false",
    }


def test_node_agent_class_builds_shell_command_with_nvm():
    command = get_agent_class("qwen").build_shell_command(
        Path("/home/ubuntu/project"),
        ["qwen", "--help"],
        {"TOKEN": "abc"},
    )

    assert command.startswith("export NVM_DIR=")
    assert "export TOKEN=abc" in command
    assert "cd /home/ubuntu/project" in command
    assert "exec qwen --help" in command


def test_non_node_agent_class_does_not_require_nvm():
    assert get_agent_class("claude").needs_nvm() is False
    assert get_agent_class("codeforge").needs_nvm() is False
    assert get_agent_class("codex").needs_nvm() is True
