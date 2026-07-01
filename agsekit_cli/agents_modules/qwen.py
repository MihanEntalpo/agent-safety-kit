from .base import BaseAgent


class QwenAgent(BaseAgent):
    type_name = "qwen"
    runtime_binary = "qwen"
    default_version = "0.15.11"
    _needs_nvm = True
    config_dir_env_name = "QWEN_HOME"
    config_dir_relative_path = ".qwen"
    legacy_home_allow_paths = (".qwen",)
