from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Union

from .config import MountConfig, load_config, load_mounts_config, resolve_config_path
from .i18n import tr
from .vm import MultipassError, ensure_multipass_available


class MountAlreadyMountedError(RuntimeError):
    """Raised when multipass reports the mount already exists."""


def normalize_path(path: Path) -> Path:
    return path.expanduser().resolve()


def load_mounts_from_config(config_path: Optional[Union[str, Path]]) -> List[MountConfig]:
    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    config = load_config(resolved_path)
    return load_mounts_config(config)


def find_mount_by_source(mounts: Iterable[MountConfig], source: Path) -> Optional[MountConfig]:
    normalized = normalize_path(source)
    for mount in mounts:
        if mount.source == normalized:
            return mount
    return None


def _is_already_mounted_error(stderr: str) -> bool:
    return "already mounted" in stderr.lower()


def _run_multipass(command: list[str], error_message: str, *, allow_already_mounted: bool = False) -> None:
    ensure_multipass_available()
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if allow_already_mounted and stderr and _is_already_mounted_error(stderr):
            raise MountAlreadyMountedError(stderr)
        raise MultipassError(stderr or error_message)


def mount_directory(mount: MountConfig) -> None:
    _run_multipass(
        ["multipass", "mount", str(mount.source), f"{mount.vm_name}:{mount.target}"],
        tr("mounts.mount_failed", source=mount.source, vm_name=mount.vm_name, target=mount.target),
        allow_already_mounted=True,
    )


def umount_directory(mount: MountConfig) -> None:
    _run_multipass(
        ["multipass", "umount", f"{mount.vm_name}:{mount.target}"],
        tr("mounts.umount_failed", vm_name=mount.vm_name, target=mount.target),
    )
