from .base import BaseAgent


class QwenAgent(BaseAgent):
    type_name = "qwen"
    runtime_binary = "qwen"
    _needs_nvm = True
