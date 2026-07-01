from .base import BaseAgent


class CodexAgent(BaseAgent):
    type_name = "codex"
    runtime_binary = "codex"
    default_version = "0.130.0"
    _needs_nvm = True
    config_dir_env_name = "CODEX_HOME"
    config_dir_relative_path = ".codex"
    legacy_home_allow_paths = (".codex",)
