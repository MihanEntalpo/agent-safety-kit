from .base import BaseAgent
from ..agent_version_sources import latest_npm_version


class CodexAgent(BaseAgent):
    type_name = "codex"
    runtime_binary = "codex"
    default_version = "0.130.0"
    _needs_nvm = True

    @classmethod
    def check_latest_version(cls, *, architecture=None, timeout=30.0):
        del architecture
        return cls.normalize_version(latest_npm_version("@openai/codex", timeout=timeout))
