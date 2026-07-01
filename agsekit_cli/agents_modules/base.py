from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from ..config import AgentConfig


NVM_LOAD_SNIPPET = (
    "export NVM_DIR=${NVM_DIR:-$HOME/.nvm}; "
    "if [ -s \"$NVM_DIR/nvm.sh\" ]; then . \"$NVM_DIR/nvm.sh\"; "
    "elif [ -s \"$NVM_DIR/bash_completion\" ]; then . \"$NVM_DIR/bash_completion\"; fi"
)
GUEST_USER_HOME = "/home/ubuntu"
AGENT_HOMES_ROOT = f"{GUEST_USER_HOME}/.agent-homes"
PATH_EXPORT_SNIPPET = f'export PATH="/usr/local/bin:$HOME/.local/bin:{GUEST_USER_HOME}/.local/bin:$PATH"'
SEMVER_RE = re.compile(r"(?<!\d)v?(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)")
DIRECTORY_ENV_KEYS = {
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "XDG_STATE_HOME",
    "CODEX_HOME",
    "QWEN_HOME",
    "FORGE_CONFIG",
    "OPENCODE_CONFIG_DIR",
    "CLAUDE_CONFIG_DIR",
    "CLINE_DATA_DIR",
}


class BaseAgent:
    type_name = ""
    runtime_binary = ""
    installer_playbook = ""
    default_version = ""
    default_env: Dict[str, str] = {}
    _needs_nvm = False
    config_dir_env_name = ""
    config_dir_relative_path = ""
    legacy_home_allow_paths: Tuple[str, ...] = ()

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
    def migration_allow_paths(cls) -> Tuple[str, ...]:
        return cls.legacy_home_allow_paths

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
        env = self.build_isolated_home_env()
        env.update(self.default_env)
        env.update(self.agent.env)
        return env

    def build_isolated_home_env(self) -> Dict[str, str]:
        home = self.agent_home()
        env = {
            "HOME": home,
            "XDG_CONFIG_HOME": f"{home}/.config",
            "XDG_DATA_HOME": f"{home}/.local/share",
            "XDG_CACHE_HOME": f"{home}/.cache",
            "XDG_STATE_HOME": f"{home}/.local/state",
        }
        if self.needs_nvm():
            env["NVM_DIR"] = f"{GUEST_USER_HOME}/.nvm"
        if self.config_dir_env_name and self.config_dir_relative_path:
            env[self.config_dir_env_name] = f"{home}/{self.config_dir_relative_path}"
        return env

    def agent_home(self) -> str:
        safe_name = quote(self.agent.name, safe="-_.@")
        return f"{AGENT_HOMES_ROOT}/{safe_name}"

    @classmethod
    def build_shell_command(
        cls,
        workdir: Path,
        agent_command: Sequence[str],
        env_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        effective_env = {} if env_vars is None else dict(env_vars)
        parts: List[str] = []
        exports = _export_statements(effective_env)
        if exports:
            parts.append("; ".join(exports))
        mkdir_command = _mkdir_command_for_env(effective_env)
        if mkdir_command:
            parts.append(mkdir_command)
        if cls.needs_nvm():
            parts.append(NVM_LOAD_SNIPPET)
        parts.append(PATH_EXPORT_SNIPPET)
        parts.append(f"cd {shlex.quote(str(workdir))}")
        parts.append(f"exec {shlex.join(list(agent_command))}")
        return " && ".join(parts)


def _export_statements(env_vars: Dict[str, str]) -> List[str]:
    exports: List[str] = []
    for key, value in env_vars.items():
        exports.append(f"export {key}={shlex.quote(str(value))}")
    return exports


def _mkdir_command_for_env(env_vars: Dict[str, str]) -> str:
    paths = [
        str(value)
        for key, value in env_vars.items()
        if key in DIRECTORY_ENV_KEYS and str(value).startswith("/")
    ]
    if not paths:
        return ""
    quoted_paths = " ".join(shlex.quote(path) for path in paths)
    return f"mkdir -p {quoted_paths}"
