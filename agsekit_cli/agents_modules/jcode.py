from .base import BaseAgent
from ..agent_version_sources import latest_github_release_version


class JcodeAgent(BaseAgent):
    type_name = "jcode"
    runtime_binary = "jcode"
    default_version = "0.99.1"

    @classmethod
    def check_latest_version(cls, *, architecture=None, timeout=30.0):
        del architecture
        return cls.normalize_version(
            latest_github_release_version("1jehuang/jcode", tag_prefix="v", timeout=timeout)
        )
