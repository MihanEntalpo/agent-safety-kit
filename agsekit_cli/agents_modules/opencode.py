from .base import BaseAgent


class OpencodeAgent(BaseAgent):
    type_name = "opencode"
    runtime_binary = "opencode"
    _needs_nvm = True
