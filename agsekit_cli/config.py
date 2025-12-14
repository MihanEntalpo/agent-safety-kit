from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

CONFIG_ENV_VAR = "CONFIG_PATH"
DEFAULT_CONFIG_PATH = Path("config.yaml")


@dataclass
class MountConfig:
    source: Path
    target: Path
    backup: Path
    interval_minutes: int = 5
    vm_name: str = ""


@dataclass
class VmConfig:
    name: str
    cpu: int
    ram: str
    disk: str
    cloud_init: Dict[str, Any]


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


def _require_positive_int(value: Any, field_name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ConfigError(f"{field_name} must be an integer")
    if result <= 0:
        raise ConfigError(f"{field_name} must be greater than zero")
    return result


def _validate_size_field(value: Any, field_name: str) -> str:
    if isinstance(value, (str, int, float)) and str(value).strip():
        return str(value)
    raise ConfigError(f"{field_name} must be a non-empty string or number")


def load_vms_config(config: Dict[str, Any]) -> Dict[str, VmConfig]:
    raw_vms = config.get("vms")
    if not isinstance(raw_vms, dict) or not raw_vms:
        raise ConfigError("Config must include a non-empty `vms` mapping")

    vms: Dict[str, VmConfig] = {}
    for vm_name, raw_entry in raw_vms.items():
        if not isinstance(raw_entry, dict):
            raise ConfigError(f"VM `{vm_name}` must be a mapping of its parameters")

        missing = [field for field in ("cpu", "ram", "disk") if field not in raw_entry]
        if missing:
            raise ConfigError(f"VM `{vm_name}` is missing fields: {', '.join(missing)}")

        vms[vm_name] = VmConfig(
            name=str(vm_name),
            cpu=_require_positive_int(raw_entry.get("cpu"), f"vms.{vm_name}.cpu"),
            ram=_validate_size_field(raw_entry.get("ram"), f"vms.{vm_name}.ram"),
            disk=_validate_size_field(raw_entry.get("disk"), f"vms.{vm_name}.disk"),
            cloud_init=raw_entry.get("cloud-init") or {},
        )

    return vms


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


def _default_vm_name(config: Dict[str, Any]) -> Optional[str]:
    vms_section = config.get("vms")
    if isinstance(vms_section, dict) and vms_section:
        return next(iter(vms_section.keys()))
    return None


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

    default_vm = _default_vm_name(config)
    if raw_mounts and default_vm is None:
        raise ConfigError("Config must include `vms` section to infer target VM for mounts")

    mounts: List[MountConfig] = []
    for index, entry in enumerate(raw_mounts):
        if not isinstance(entry, dict):
            raise ConfigError(f"Mount entry #{index + 1} must be a mapping")

        if "source" not in entry:
            raise ConfigError(f"Mount entry #{index + 1} is missing `source`")

        source = _ensure_path(entry.get("source"), f"mounts[{index}].source")
        target_raw = entry.get("target")
        backup_raw = entry.get("backup")
        vm_name = entry.get("vm") or default_vm
        if not vm_name:
            raise ConfigError(f"Mount entry #{index + 1} is missing `vm` and no default VM is configured")

        target = _ensure_path(target_raw, f"mounts[{index}].target") if target_raw else _default_target(source)
        backup = _ensure_path(backup_raw, f"mounts[{index}].backup") if backup_raw else _default_backup(source)
        interval_minutes = _normalize_interval(entry.get("interval"))

        mounts.append(
            MountConfig(
                source=source,
                target=target,
                backup=backup,
                interval_minutes=interval_minutes,
                vm_name=str(vm_name),
            )
        )

    return mounts
