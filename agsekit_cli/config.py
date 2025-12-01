from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml

CONFIG_ENV_VAR = "CONFIG_PATH"
DEFAULT_CONFIG_PATH = Path("config.yaml")


@dataclass
class MountConfig:
    source: Path
    target: Path
    backup: Path
    interval_minutes: int = 5


class ConfigError(RuntimeError):
    """Raised when configuration cannot be loaded."""


def resolve_config_path(explicit_path: Path | None = None) -> Path:
    env_path = os.environ.get(CONFIG_ENV_VAR)
    base_path = explicit_path or (Path(env_path) if env_path else DEFAULT_CONFIG_PATH)
    return base_path.expanduser()


def load_config(path: Path | None = None) -> Dict[str, Any]:
    config_path = resolve_config_path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping")

    return data


def load_vm_config(config: Dict[str, Any]) -> Dict[str, Any]:
    vm_config = config.get("vm")
    if not isinstance(vm_config, dict):
        raise ConfigError("Config must include a `vm` mapping")

    required_keys = ["cpu", "ram", "disk", "name"]
    missing = [key for key in required_keys if key not in vm_config]
    if missing:
        raise ConfigError(f"Missing VM fields: {', '.join(missing)}")

    return vm_config


def _ensure_path(value: Any, field_name: str) -> Path:
    if isinstance(value, Path):
        path = value
    elif isinstance(value, str):
        path = Path(value)
    else:
        raise ConfigError(f"{field_name} must be a string path")
    return path.expanduser().resolve()


def _default_target(source: Path) -> Path:
    return Path("/home/ubuntu") / source.name


def _default_backup(source: Path) -> Path:
    return source.parent / f"backups-{source.name}"


def _normalize_interval(raw_value: Any) -> int:
    if raw_value is None:
        return 5
    try:
        interval = int(raw_value)
    except (TypeError, ValueError):
        raise ConfigError("Mount interval must be an integer")
    if interval <= 0:
        raise ConfigError("Mount interval must be greater than zero")
    return interval


def load_mounts_config(config: Dict[str, Any]) -> List[MountConfig]:
    raw_mounts = config.get("mounts") or []
    if not isinstance(raw_mounts, list):
        raise ConfigError("Config `mounts` must be a list")

    mounts: List[MountConfig] = []
    for index, entry in enumerate(raw_mounts):
        if not isinstance(entry, dict):
            raise ConfigError(f"Mount entry #{index + 1} must be a mapping")

        if "source" not in entry:
            raise ConfigError(f"Mount entry #{index + 1} is missing `source`")

        source = _ensure_path(entry.get("source"), f"mounts[{index}].source")
        target_raw = entry.get("target")
        backup_raw = entry.get("backup")

        target = _ensure_path(target_raw, f"mounts[{index}].target") if target_raw else _default_target(source)
        backup = _ensure_path(backup_raw, f"mounts[{index}].backup") if backup_raw else _default_backup(source)
        interval_minutes = _normalize_interval(entry.get("interval"))

        mounts.append(MountConfig(source=source, target=target, backup=backup, interval_minutes=interval_minutes))

    return mounts
