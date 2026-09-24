from .base import BaseAgent
from ..agent_version_sources import latest_pypi_version


class AiderAgent(BaseAgent):
    type_name = "aider"
    runtime_binary = "aider"
    default_version = "0.86.2"
    default_env = {"AIDER_CHECK_UPDATE": "false"}

    @classmethod
    def check_latest_version(cls, *, architecture=None, timeout=30.0):
        del architecture
        return cls.normalize_version(latest_pypi_version("aider-chat", timeout=timeout))
