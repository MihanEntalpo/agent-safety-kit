from .base import BaseAgent
from ..agent_version_sources import latest_github_release_version


class ForgecodeAgent(BaseAgent):
    type_name = "forgecode"
    runtime_binary = "forge"
    default_version = "2.12.14"
    default_env = {"FORGE_TRACKER": "false"}

    @classmethod
    def check_latest_version(cls, *, architecture=None, timeout=30.0):
        del architecture
        return cls.normalize_version(
            latest_github_release_version("tailcallhq/forgecode", tag_prefix="v", timeout=timeout)
        )
