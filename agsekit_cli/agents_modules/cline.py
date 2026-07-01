from .base import BaseAgent


class ClineAgent(BaseAgent):
    type_name = "cline"
    runtime_binary = "cline"
    default_version = "2.17.0"
    default_env = {"CLINE_NO_AUTO_UPDATE": "1"}
    _needs_nvm = True
    config_dir_env_name = "CLINE_DATA_DIR"
    config_dir_relative_path = ".cline/data"
    legacy_home_allow_paths = (".cline", ".config/cline", ".local/share/cline")
