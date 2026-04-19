from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Iterable, Optional

MULTIPASS_WINDOWS_INSTALL_URL = "https://canonical.com/multipass/install"


def is_windows() -> bool:
    return platform.system() == "Windows"


def windows_multipass_exe_path() -> Path:
    configured = os.environ.get("AGSEKIT_MULTIPASS_EXE")
    return Path(configured) if configured else Path("C:/Program Files/Multipass/bin/multipass.exe")


def msys2_root() -> Path:
    configured = os.environ.get("AGSEKIT_MSYS2_ROOT") or os.environ.get("MSYS2_ROOT")
    return Path(configured) if configured else Path("C:/msys64")


def msys2_bin_dir() -> Path:
    return msys2_root() / "usr" / "bin"


def windows_tool_candidates(name: str) -> Iterable[Path]:
    normalized = name.lower()
    if normalized in {"multipass", "multipass.exe"}:
        yield windows_multipass_exe_path()
        return

    msys_name = normalized if normalized.endswith(".exe") else f"{normalized}.exe"
    if normalized in {"rsync", "rsync.exe", "ssh", "ssh.exe", "ssh-keygen", "ssh-keygen.exe", "bash", "bash.exe"}:
        yield msys2_bin_dir() / msys_name


def resolve_host_tool(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found

    if not is_windows():
        return None

    for candidate in windows_tool_candidates(name):
        if candidate.exists():
            return str(candidate)
    return None


def host_tool_command(name: str) -> str:
    if shutil.which(name):
        return name
    if is_windows():
        for candidate in windows_tool_candidates(name):
            if candidate.exists():
                return str(candidate)
    return name


def host_tool_exists(name: str) -> bool:
    return resolve_host_tool(name) is not None


def multipass_command() -> str:
    return host_tool_command("multipass")


def rsync_command() -> str:
    return host_tool_command("rsync")


def ssh_command() -> str:
    return host_tool_command("ssh")


def ssh_keygen_command() -> str:
    return host_tool_command("ssh-keygen")
