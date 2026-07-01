from .base import BaseAgent


class OpencodeAgent(BaseAgent):
    type_name = "opencode"
    runtime_binary = "opencode"
    default_version = "1.14.50"
    default_env = {"OPENCODE_DISABLE_AUTOUPDATE": "true"}
    _needs_nvm = True
    config_dir_env_name = "OPENCODE_CONFIG_DIR"
    config_dir_relative_path = ".config/opencode"
    legacy_home_allow_paths = (".config/opencode", ".local/share/opencode", ".cache/opencode")
