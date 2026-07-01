from .base import BaseAgent


class ForgecodeAgent(BaseAgent):
    type_name = "forgecode"
    runtime_binary = "forge"
    default_version = "2.12.14"
    default_env = {"FORGE_TRACKER": "false"}
    config_dir_env_name = "FORGE_CONFIG"
    config_dir_relative_path = "forge"
    legacy_home_allow_paths = (".forge", "forge", ".config/forge", ".local/share/forge")
