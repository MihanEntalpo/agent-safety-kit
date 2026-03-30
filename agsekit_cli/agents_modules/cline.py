from .base import BaseAgent


class ClineAgent(BaseAgent):
    type_name = "cline"
    runtime_binary = "cline"
    _needs_nvm = True
