from .base import BaseAgent
from ..agent_version_sources import latest_github_release_version


class CodexGlibcAgent(BaseAgent):
    type_name = "codex-glibc"
    runtime_binary = "codex-glibc"
    default_version = "0.130.0"

    @classmethod
    def check_latest_version(cls, *, architecture=None, timeout=30.0):
        del architecture
        return cls.normalize_version(
            latest_github_release_version("openai/codex", tag_prefix="rust-v", timeout=timeout)
        )
