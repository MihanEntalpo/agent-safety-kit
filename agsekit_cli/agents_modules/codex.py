from .base import BaseAgent


class CodexAgent(BaseAgent):
    type_name = "codex"
    runtime_binary = "codex"
    default_version = "0.130.0"
    _needs_nvm = True
