from .base import BaseAgent


class CodexGlibcPrebuiltAgent(BaseAgent):
    type_name = "codex-glibc-prebuilt"
    runtime_binary = "codex-glibc-prebuilt"
    default_version = "0.130.0"
    config_dir_env_name = "CODEX_HOME"
    config_dir_relative_path = ".codex"
    legacy_home_allow_paths = (".codex",)
