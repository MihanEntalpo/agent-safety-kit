from .base import BaseAgent
from ..agent_version_sources import latest_npm_version


class QwenAgent(BaseAgent):
    type_name = "qwen"
    runtime_binary = "qwen"
    default_version = "0.15.11"
    _needs_nvm = True

    @classmethod
    def check_latest_version(cls, *, architecture=None, timeout=30.0):
        del architecture
        return cls.normalize_version(latest_npm_version("@qwen-code/qwen-code", timeout=timeout))
