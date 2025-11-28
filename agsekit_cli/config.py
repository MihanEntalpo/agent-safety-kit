from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

CONFIG_ENV_VAR = "CONFIG_PATH"
DEFAULT_CONFIG_PATH = Path("config.yaml")


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
