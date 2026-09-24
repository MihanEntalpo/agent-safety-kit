from .base import BaseAgent
from ..agent_version_sources import latest_npm_version


class OpencodeAgent(BaseAgent):
    type_name = "opencode"
    runtime_binary = "opencode"
    default_version = "1.14.50"
    default_env = {"OPENCODE_DISABLE_AUTOUPDATE": "true"}
    _needs_nvm = True

    @classmethod
    def check_latest_version(cls, *, architecture=None, timeout=30.0):
        del architecture
        return cls.normalize_version(latest_npm_version("opencode-ai", timeout=timeout))
