from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple, Union

from .config import ConfigError, MountConfig, load_config, load_mounts_config, resolve_config_path
from .debug import debug_log_command, debug_log_result
from .host_tools import multipass_command, run_multipass_subprocess
from .i18n import tr
from .vm import MultipassError, ensure_multipass_available


class MountAlreadyMountedError(RuntimeError):
    """Raised when multipass reports the mount already exists."""


RegisteredMount = Tuple[Optional[Path], Optional[Path]]
# Multipass mount metadata is not stable enough to rely on a single key name.
# We accept the known variants here so doctor/run can recognize real mounts
# across Multipass versions and output shapes.
_MOUNT_SOURCE_KEYS = ("source", "source_path", "source path", "host_path", "host path", "local_path", "local path")
_MOUNT_TARGET_KEYS = ("mount_path", "mount path", "target", "target_path", "target path", "destination", "path")


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


def find_mount_by_path(mounts: Iterable[MountConfig], source: Path) -> Optional[MountConfig]:
    normalized = normalize_path(source)
    matches: List[MountConfig] = []
    for mount in mounts:
        if normalized == mount.source:
            matches.append(mount)
            continue
        try:
            normalized.relative_to(mount.source)
        except ValueError:
            continue
        matches.append(mount)

    if not matches:
        return None

    matches.sort(key=lambda mount: len(mount.source.parts), reverse=True)
    longest = len(matches[0].source.parts)
    if sum(1 for mount in matches if len(mount.source.parts) == longest) > 1:
        raise ConfigError(tr("mounts.source_ambiguous", source=normalized))
    return matches[0]


def _is_already_mounted_error(stderr: str) -> bool:
    return "already mounted" in stderr.lower()


def _coerce_path(value: object) -> Optional[Path]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower() in {"none", "null"} or text in {"~", "--"}:
        return None
    return Path(text).expanduser().resolve()


def _extract_path_from_mapping(mapping: dict[object, object], keys: tuple[str, ...]) -> Optional[Path]:
    for key in keys:
        candidate = mapping.get(key)
        path = _coerce_path(candidate)
        if path is not None:
            return path
    return None


def _extract_registered_mounts(raw_mounts: object) -> list[RegisteredMount]:
    if raw_mounts is None:
        return []

    if isinstance(raw_mounts, list):
        mounts: list[RegisteredMount] = []
        for item in raw_mounts:
            mounts.extend(_extract_registered_mounts(item))
        return mounts

    if isinstance(raw_mounts, dict):
        # Some Multipass versions emit one mount as a single mapping with
        # explicit source/target fields instead of a source->target map.
        direct_source = _extract_path_from_mapping(raw_mounts, _MOUNT_SOURCE_KEYS)
        direct_target = _extract_path_from_mapping(raw_mounts, _MOUNT_TARGET_KEYS)
        if direct_source is not None or direct_target is not None:
            return [(direct_source, direct_target)]

        mounts: list[RegisteredMount] = []
        for key, value in raw_mounts.items():
            # Other variants use the host path as the dict key.
            keyed_source = _coerce_path(key)

            if isinstance(value, str):
                mounts.append((keyed_source, _coerce_path(value)))
                continue

            if isinstance(value, dict):
                # Nested mappings can mix both styles, so keep checking the
                # explicit aliases before descending recursively.
                nested_source = _extract_path_from_mapping(value, _MOUNT_SOURCE_KEYS) or keyed_source
                nested_target = _extract_path_from_mapping(value, _MOUNT_TARGET_KEYS)
                if nested_source is not None or nested_target is not None:
                    mounts.append((nested_source, nested_target))
                    continue

            mounts.extend(_extract_registered_mounts(value))
        return mounts

    return []


def load_multipass_mounts(*, debug: bool = False) -> Dict[str, Set[RegisteredMount]]:
    ensure_multipass_available()
    command = [multipass_command(), "info", "--format", "json"]
    debug_log_command(command, enabled=debug)
    result = run_multipass_subprocess(command, check=False, capture_output=True)
    debug_log_result(result, enabled=debug)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise MultipassError(details or tr("mounts.info_failed"))

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MultipassError(tr("mounts.info_parse_failed")) from exc

    info = payload.get("info")
    if not isinstance(info, dict):
        raise MultipassError(tr("mounts.info_parse_failed"))

    mounts_by_vm: Dict[str, Set[RegisteredMount]] = {}
    for vm_name, entry in info.items():
        if not isinstance(vm_name, str) or not isinstance(entry, dict):
            continue
        # Normalize mount registrations once here so higher-level checks can
        # reason about "is this mount really attached?" without parsing raw JSON.
        mounts_by_vm[vm_name] = set(_extract_registered_mounts(entry.get("mounts")))
    return mounts_by_vm


def is_mount_registered(mount: MountConfig, mounted_by_vm: Dict[str, Set[RegisteredMount]]) -> bool:
    for source, target in mounted_by_vm.get(mount.vm_name, set()):
        if source is not None and target is not None:
            if source == mount.source and target == mount.target:
                return True
            continue
        if target is not None and target == mount.target:
            return True
        if source is not None and source == mount.source:
            return True
    return False


def host_path_has_entries(path: Path) -> Optional[bool]:
    normalized = normalize_path(path)
    if not normalized.exists() or not normalized.is_dir():
        return None
    iterator = normalized.iterdir()
    return next(iterator, None) is not None


def vm_path_has_entries(vm_name: str, path: Path, *, debug: bool = False) -> bool:
    ensure_multipass_available()
    quoted_path = shlex.quote(str(path))
    script = (
        f"path={quoted_path}; "
        "if [ ! -d \"$path\" ]; then printf 'missing'; "
        "elif find \"$path\" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then printf 'non-empty'; "
        "else printf 'empty'; fi"
    )
    command = [multipass_command(), "exec", vm_name, "--", "bash", "-lc", script]
    debug_log_command(command, enabled=debug)
    result = run_multipass_subprocess(command, check=False, capture_output=True)
    debug_log_result(result, enabled=debug)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise MultipassError(tr("mounts.check_failed", vm_name=vm_name, target=path, details=f": {details}" if details else ""))

    marker = result.stdout.strip()
    if marker == "non-empty":
        return True
    if marker in {"empty", "missing"}:
        return False
    raise MultipassError(tr("mounts.check_unexpected_output", vm_name=vm_name, target=path, output=marker or "<empty>"))


def _run_multipass(command: list[str], error_message: str, *, allow_already_mounted: bool = False) -> None:
    ensure_multipass_available()
    debug_log_command(command)
    result = run_multipass_subprocess(command, check=False, capture_output=True)
    debug_log_result(result)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if allow_already_mounted and stderr and _is_already_mounted_error(stderr):
            raise MountAlreadyMountedError(stderr)
        raise MultipassError(stderr or error_message)


def mount_directory(mount: MountConfig) -> None:
    _run_multipass(
        [multipass_command(), "mount", str(mount.source), f"{mount.vm_name}:{mount.target}"],
        tr("mounts.mount_failed", source=mount.source, vm_name=mount.vm_name, target=mount.target),
        allow_already_mounted=True,
    )


def umount_directory(mount: MountConfig) -> None:
    _run_multipass(
        [multipass_command(), "umount", f"{mount.vm_name}:{mount.target}"],
        tr("mounts.umount_failed", vm_name=mount.vm_name, target=mount.target),
    )
