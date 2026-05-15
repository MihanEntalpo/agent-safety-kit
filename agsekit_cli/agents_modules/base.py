from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import AgentConfig


NVM_LOAD_SNIPPET = (
    "export NVM_DIR=${NVM_DIR:-$HOME/.nvm}; "
    "if [ -s \"$NVM_DIR/nvm.sh\" ]; then . \"$NVM_DIR/nvm.sh\"; "
    "elif [ -s \"$NVM_DIR/bash_completion\" ]; then . \"$NVM_DIR/bash_completion\"; fi"
)
PATH_EXPORT_SNIPPET = 'export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"'
SEMVER_RE = re.compile(r"(?<!\d)v?(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)")


class BaseAgent:
    type_name = ""
    runtime_binary = ""
    installer_playbook = ""
    default_version = ""
    default_env: Dict[str, str] = {}
    _needs_nvm = False

    def __init__(self, agent: "AgentConfig"):
        self.agent = agent

    @classmethod
    def needs_nvm(cls) -> bool:
        return bool(cls._needs_nvm)

    @classmethod
    def playbook_name(cls) -> str:
        if cls.installer_playbook:
            return cls.installer_playbook
        return f"{cls.type_name}.yml"

    @classmethod
    def normalize_version(cls, version: str) -> str:
        cleaned = str(version).strip()
        if cleaned.startswith("v"):
            cleaned = cleaned[1:]
        match = SEMVER_RE.fullmatch(cleaned)
        if match is None:
            raise ValueError(f"Unsupported {cls.type_name} version format: {version}")
        return match.group(1)

    @classmethod
    def extract_version(cls, output: str) -> Optional[str]:
        match = SEMVER_RE.search(output)
        if match is None:
            return None
        return cls.normalize_version(match.group(1))

    @classmethod
    def build_binary_check_command(cls) -> str:
        parts: List[str] = [PATH_EXPORT_SNIPPET]
        if cls.needs_nvm():
            parts.insert(0, NVM_LOAD_SNIPPET)
        parts.append(f"command -v {shlex.quote(cls.runtime_binary)} >/dev/null 2>&1")
        return " && ".join(parts)

    @classmethod
    def build_version_command(cls) -> str:
        parts: List[str] = [PATH_EXPORT_SNIPPET]
        if cls.needs_nvm():
            parts.insert(0, NVM_LOAD_SNIPPET)
            parts.append("nvm use --silent default >/dev/null 2>&1 || true")
        parts.extend(
            [
                f"command -v {shlex.quote(cls.runtime_binary)} >/dev/null 2>&1",
                f"{shlex.quote(cls.runtime_binary)} --version 2>&1",
            ]
        )
        return " && ".join(parts)

    def build_env(self) -> Dict[str, str]:
        env = dict(self.default_env)
        env.update(self.agent.env)
        return env

    @classmethod
    def build_shell_command(
        cls,
        workdir: Path,
        agent_command: Sequence[str],
        env_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        effective_env = {} if env_vars is None else dict(env_vars)
        parts: List[str] = []
        if cls.needs_nvm():
            parts.append(NVM_LOAD_SNIPPET)
        exports = _export_statements(effective_env)
        if exports:
            parts.append("; ".join(exports))
        parts.append(f"cd {shlex.quote(str(workdir))}")
        parts.append(f"exec {shlex.join(list(agent_command))}")
        return " && ".join(parts)


def _export_statements(env_vars: Dict[str, str]) -> List[str]:
    exports: List[str] = []
    for key, value in env_vars.items():
        exports.append(f"export {key}={shlex.quote(str(value))}")
    return exports
