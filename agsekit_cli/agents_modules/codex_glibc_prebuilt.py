from .base import BaseAgent


class CodexGlibcPrebuiltAgent(BaseAgent):
    type_name = "codex-glibc-prebuilt"
    runtime_binary = "codex-glibc-prebuilt"
    default_version = "0.130.0"
