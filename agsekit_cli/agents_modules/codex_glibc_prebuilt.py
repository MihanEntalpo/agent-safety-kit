from .base import BaseAgent
from ..agent_version_sources import AgentVersionCheckError
from ..prebuilt import PrebuiltReleaseError, resolve_codex_glibc_prebuilt_release


class CodexGlibcPrebuiltAgent(BaseAgent):
    type_name = "codex-glibc-prebuilt"
    runtime_binary = "codex-glibc-prebuilt"
    default_version = "0.130.0"

    @classmethod
    def check_latest_version(cls, *, architecture=None, timeout=30.0):
        del timeout
        if not architecture:
            raise AgentVersionCheckError("Current architecture is required for codex-glibc-prebuilt")
        try:
            release = resolve_codex_glibc_prebuilt_release(arch=architecture)
        except PrebuiltReleaseError as exc:
            raise AgentVersionCheckError(str(exc)) from exc
        prefix = "codex-glibc-rust-v"
        if not release.tag.startswith(prefix):
            raise AgentVersionCheckError(f"Unexpected codex-glibc prebuilt tag: {release.tag}")
        return cls.normalize_version(release.tag[len(prefix):])
