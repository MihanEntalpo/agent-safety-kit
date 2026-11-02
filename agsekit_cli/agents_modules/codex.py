from .base import BaseAgent
from ..agent_version_sources import latest_github_release_version


class CodexAgent(BaseAgent):
    type_name = "codex"
    runtime_binary = "codex"
    default_version = "0.166.0"
    _needs_nvm = False

    @classmethod
    def check_latest_version(cls, *, architecture=None, timeout=30.0):
        del architecture
        return cls.normalize_version(
            latest_github_release_version("openai/codex", tag_prefix="rust-v", timeout=timeout)
        )
