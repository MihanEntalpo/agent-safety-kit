from __future__ import annotations

import locale
import os
import platform
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional, Sequence

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


def _windows_code_page_name(getter_name: str) -> Optional[str]:
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        getter = getattr(kernel32, getter_name, None)
        if getter is None:
            return None

        code_page = int(getter())
    except (AttributeError, OSError, ValueError):
        return None

    if code_page <= 0:
        return None
    return f"cp{code_page}"


def _windows_registry_code_pages() -> tuple[str, ...]:
    try:
        import winreg
    except ImportError:
        return ()

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Nls\CodePage") as key:
            values = []
            for name in ("ACP", "OEMCP", "MACCP"):
                raw_value, _value_type = winreg.QueryValueEx(key, name)
                if not raw_value:
                    continue
                code_page = f"cp{str(raw_value).strip()}"
                if code_page not in values:
                    values.append(code_page)
    except OSError:
        return ()

    return tuple(values)


@lru_cache(maxsize=1)
def windows_output_encodings() -> tuple[str, ...]:
    encodings: list[str] = ["utf-8"]

    for getter_name in ("GetConsoleOutputCP", "GetOEMCP", "GetACP"):
        code_page = _windows_code_page_name(getter_name)
        if code_page and code_page not in encodings:
            encodings.append(code_page)

    for code_page in _windows_registry_code_pages():
        if code_page not in encodings:
            encodings.append(code_page)

    preferred = locale.getpreferredencoding(False)
    if preferred and preferred not in encodings:
        encodings.append(preferred)

    if "mbcs" not in encodings:
        encodings.append("mbcs")

    return tuple(encodings)


def decode_windows_output(data: bytes) -> str:
    if not data:
        return ""

    for encoding in windows_output_encodings():
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    return data.decode(windows_output_encodings()[-1], errors="replace")


def run_multipass_subprocess(
    command: Sequence[str],
    *,
    check: bool = False,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    if not is_windows() or not capture_output:
        return subprocess.run(command, check=check, capture_output=capture_output, text=True)

    raw_result = subprocess.run(command, check=False, capture_output=True, text=False)
    result = subprocess.CompletedProcess(
        raw_result.args,
        raw_result.returncode,
        decode_windows_output(raw_result.stdout or b""),
        decode_windows_output(raw_result.stderr or b""),
    )
    if check:
        result.check_returncode()
    return result
