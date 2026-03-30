from .base import BaseAgent


class CodexAgent(BaseAgent):
    type_name = "codex"
    runtime_binary = "codex"
    _needs_nvm = True
