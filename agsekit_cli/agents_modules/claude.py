from .base import BaseAgent
from ..agent_version_sources import latest_npm_version


class ClaudeAgent(BaseAgent):
    type_name = "claude"
    runtime_binary = "claude"
    default_version = "2.1.141"
    default_env = {"DISABLE_AUTOUPDATER": "1"}
    _needs_nvm = True

    @classmethod
    def check_latest_version(cls, *, architecture=None, timeout=30.0):
        del architecture
        return cls.normalize_version(latest_npm_version("@anthropic-ai/claude-code", timeout=timeout))
