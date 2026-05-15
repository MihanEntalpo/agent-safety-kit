from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agsekit_cli.agents_modules import (
    AGENT_RUNTIME_BINARIES,
    DEFAULT_AGENT_VERSIONS,
    SUPPORTED_AGENT_TYPES,
    build_agent_module,
    get_agent_class,
)
from agsekit_cli.config import AgentConfig


def test_supported_agent_types_match_runtime_mapping():
    assert tuple(AGENT_RUNTIME_BINARIES.keys()) == SUPPORTED_AGENT_TYPES
    assert AGENT_RUNTIME_BINARIES["aider"] == "aider"
    assert DEFAULT_AGENT_VERSIONS["cline"] == "2.17.0"


def test_build_agent_module_returns_specific_agent_class():
    agent = AgentConfig(name="main", type="forgecode", version="2.12.14", env={}, vm_name=None)

    module = build_agent_module(agent)

    assert module.__class__.__name__ == "ForgecodeAgent"


def test_agent_default_env_is_applied_and_user_env_can_override_it():
    agent = AgentConfig(
        name="main",
        type="forgecode",
        version="2.12.14",
        env={"TOKEN": "abc", "FORGE_TRACKER": "true"},
        vm_name=None,
    )

    module = build_agent_module(agent)

    assert module.build_env() == {
        "TOKEN": "abc",
        "FORGE_TRACKER": "true",
    }


def test_agents_with_built_in_default_envs_expose_them():
    assert build_agent_module(
        AgentConfig(name="aider", type="aider", version="0.86.2", env={}, vm_name=None)
    ).build_env()["AIDER_CHECK_UPDATE"] == "false"
    assert build_agent_module(
        AgentConfig(name="opencode", type="opencode", version="1.14.50", env={}, vm_name=None)
    ).build_env()["OPENCODE_DISABLE_AUTOUPDATE"] == "true"
    assert build_agent_module(
        AgentConfig(name="claude", type="claude", version="2.1.141", env={}, vm_name=None)
    ).build_env()["DISABLE_AUTOUPDATER"] == "1"
    assert build_agent_module(
        AgentConfig(name="cline", type="cline", version="2.17.0", env={}, vm_name=None)
    ).build_env()["CLINE_NO_AUTO_UPDATE"] == "1"


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
    assert get_agent_class("aider").needs_nvm() is False
    assert get_agent_class("forgecode").needs_nvm() is False
    assert get_agent_class("codex").needs_nvm() is True
    assert get_agent_class("claude").needs_nvm() is True
