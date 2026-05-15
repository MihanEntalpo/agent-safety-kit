from .base import BaseAgent


class CodexGlibcAgent(BaseAgent):
    type_name = "codex-glibc"
    runtime_binary = "codex-glibc"
    default_version = "0.130.0"
