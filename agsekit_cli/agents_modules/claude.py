from .base import BaseAgent


class ClaudeAgent(BaseAgent):
    type_name = "claude"
    runtime_binary = "claude"
    default_version = "2.1.141"
    default_env = {"DISABLE_AUTOUPDATER": "1"}
    _needs_nvm = True
    config_dir_env_name = "CLAUDE_CONFIG_DIR"
    config_dir_relative_path = ".claude"
    legacy_home_allow_paths = (".claude", ".claude.json")
