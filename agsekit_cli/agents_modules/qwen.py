from .base import BaseAgent


class QwenAgent(BaseAgent):
    type_name = "qwen"
    runtime_binary = "qwen"
    default_version = "0.15.11"
    _needs_nvm = True
