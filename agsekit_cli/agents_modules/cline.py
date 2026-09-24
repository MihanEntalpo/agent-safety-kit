from .base import BaseAgent
from ..agent_version_sources import latest_npm_version


class ClineAgent(BaseAgent):
    type_name = "cline"
    runtime_binary = "cline"
    default_version = "2.17.0"
    default_env = {"CLINE_NO_AUTO_UPDATE": "1"}
    _needs_nvm = True

    @classmethod
    def check_latest_version(cls, *, architecture=None, timeout=30.0):
        del architecture
        return cls.normalize_version(latest_npm_version("cline", timeout=timeout))
