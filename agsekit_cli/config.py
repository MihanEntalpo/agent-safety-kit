from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import yaml

from .i18n import tr
from .vm_bundles import normalize_install_bundles

CONFIG_ENV_VAR = "CONFIG_PATH"
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "agsekit" / "config.yaml"
ALLOWED_AGENT_TYPES = {
    "qwen": "qwen",
    "codex": "codex",
    "codex-glibc": "codex-glibc",
    "claude": "claude-code",
    "claude-code": "claude-code",
}


@dataclass
class MountConfig:
    source: Path
    target: Path
    backup: Path
    interval_minutes: int = 5
    max_backups: int = 100
    backup_clean_method: str = "thin"
    vm_name: str = ""


@dataclass
class VmConfig:
    name: str
    cpu: int
    ram: str
    disk: str
    cloud_init: Dict[str, Any]
    port_forwarding: List["PortForwardingRule"]
    proxychains: Optional[str] = None
    install: List[str] = field(default_factory=list)


@dataclass
class AgentConfig:
    name: str
    type: str
    env: Dict[str, str]
    default_args: List[str] = field(default_factory=list)
    vm_name: Optional[str] = None


class ConfigError(RuntimeError):
    """Raised when configuration cannot be loaded."""


def resolve_config_path(explicit_path: Optional[Path] = None) -> Path:
    env_path = os.environ.get(CONFIG_ENV_VAR)
    base_path = explicit_path or (Path(env_path) if env_path else DEFAULT_CONFIG_PATH)
    return base_path.expanduser()


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    config_path = resolve_config_path(path)
    if not config_path.exists():
        raise ConfigError(tr("config.file_not_found", path=config_path))

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ConfigError(tr("config.root_not_mapping"))

    return data


def _require_positive_int(value: Any, field_name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ConfigError(tr("config.field_not_int", field_name=field_name))
    if result <= 0:
        raise ConfigError(tr("config.field_not_positive", field_name=field_name))
    return result


def _validate_size_field(value: Any, field_name: str) -> str:
    if isinstance(value, (str, int, float)) and str(value).strip():
        return str(value)
    raise ConfigError(tr("config.field_not_string_or_number", field_name=field_name))


def _normalize_address(value: Any, field_name: str) -> str:
    if not isinstance(value, (str, int, float)):
        raise ConfigError(tr("config.field_not_host_port", field_name=field_name))

    text = str(value).strip()
    if ":" not in text:
        raise ConfigError(tr("config.field_missing_host_port", field_name=field_name))

    host, port_text = text.rsplit(":", 1)
    if not host:
        raise ConfigError(tr("config.field_missing_host", field_name=field_name))
    try:
        port = int(port_text)
    except ValueError:
        raise ConfigError(tr("config.field_port_not_numeric", field_name=field_name))
    if port <= 0 or port > 65535:
        raise ConfigError(tr("config.field_port_invalid", field_name=field_name))

    return f"{host}:{port}"


@dataclass
class PortForwardingRule:
    type: str
    host_addr: Optional[str]
    vm_addr: str


def _normalize_port_forwarding(raw_entry: Any, vm_name: str) -> List[PortForwardingRule]:
    if raw_entry is None:
        return []
    if not isinstance(raw_entry, list):
        raise ConfigError(tr("config.port_forwarding_not_list", vm_name=vm_name))

    rules: List[PortForwardingRule] = []
    for index, rule in enumerate(raw_entry):
        if not isinstance(rule, dict):
            raise ConfigError(tr("config.port_forwarding_not_mapping", vm_name=vm_name, index=index))

        raw_type = rule.get("type")
        if raw_type not in {"local", "remote", "socks5"}:
            raise ConfigError(
                tr("config.port_forwarding_invalid_type", vm_name=vm_name, index=index)
            )

        vm_addr_raw = rule.get("vm-addr")
        if vm_addr_raw is None:
            raise ConfigError(tr("config.port_forwarding_missing_vm_addr", vm_name=vm_name, index=index))

        host_addr: Optional[str]
        if raw_type in {"local", "remote"}:
            host_addr_raw = rule.get("host-addr")
            if host_addr_raw is None:
                raise ConfigError(tr("config.port_forwarding_missing_host_addr", vm_name=vm_name, index=index))
            host_addr = _normalize_address(host_addr_raw, f"vms.{vm_name}.port-forwarding[{index}].host-addr")
        else:
            host_addr = None

        vm_addr = _normalize_address(vm_addr_raw, f"vms.{vm_name}.port-forwarding[{index}].vm-addr")

        rules.append(
            PortForwardingRule(
                type=str(raw_type),
                host_addr=host_addr,
                vm_addr=vm_addr,
            )
        )

    return rules


def _normalize_proxychains(value: Any, vm_name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(tr("config.proxychains_not_string", vm_name=vm_name))
    cleaned = value.strip()
    if not cleaned:
        return None

    parsed = urlparse(cleaned)
    if not parsed.scheme or not parsed.hostname or not parsed.port:
        raise ConfigError(
            tr("config.proxychains_invalid_url", vm_name=vm_name)
        )
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ConfigError(tr("config.proxychains_forbidden_parts", vm_name=vm_name))

    scheme = parsed.scheme.lower()
    allowed_schemes = {"http", "https", "socks4", "socks5"}
    if scheme not in allowed_schemes:
        raise ConfigError(
            tr(
                "config.proxychains_invalid_scheme",
                vm_name=vm_name,
                schemes=", ".join(sorted(allowed_schemes)),
            )
        )

    return f"{scheme}://{parsed.hostname}:{parsed.port}"


def load_vms_config(config: Dict[str, Any]) -> Dict[str, VmConfig]:
    raw_vms = config.get("vms")
    if not isinstance(raw_vms, dict) or not raw_vms:
        raise ConfigError(tr("config.vms_missing"))

    vms: Dict[str, VmConfig] = {}
    for vm_name, raw_entry in raw_vms.items():
        if not isinstance(raw_entry, dict):
            raise ConfigError(tr("config.vm_not_mapping", vm_name=vm_name))

        missing = [field for field in ("cpu", "ram", "disk") if field not in raw_entry]
        if missing:
            raise ConfigError(tr("config.vm_missing_fields", vm_name=vm_name, missing=", ".join(missing)))

        try:
            install_bundles = normalize_install_bundles(raw_entry.get("install"), vm_name)
        except ValueError as exc:
            raise ConfigError(str(exc))

        vms[vm_name] = VmConfig(
            name=str(vm_name),
            cpu=_require_positive_int(raw_entry.get("cpu"), f"vms.{vm_name}.cpu"),
            ram=_validate_size_field(raw_entry.get("ram"), f"vms.{vm_name}.ram"),
            disk=_validate_size_field(raw_entry.get("disk"), f"vms.{vm_name}.disk"),
            cloud_init=raw_entry.get("cloud-init") or {},
            port_forwarding=_normalize_port_forwarding(raw_entry.get("port-forwarding"), vm_name),
            proxychains=_normalize_proxychains(raw_entry.get("proxychains"), vm_name),
            install=install_bundles,
        )

    return vms


def _ensure_path(value: Any, field_name: str) -> Path:
    if isinstance(value, Path):
        path = value
    elif isinstance(value, str):
        path = Path(value)
    else:
        raise ConfigError(tr("config.field_not_path", field_name=field_name))
    return path.expanduser().resolve()


def _default_target(source: Path) -> Path:
    return Path("/home/ubuntu") / source.name


def _default_backup(source: Path) -> Path:
    return source.parent / f"backups-{source.name}"


def default_mount_target(source: Path) -> Path:
    return _default_target(source)


def default_mount_backup(source: Path) -> Path:
    return _default_backup(source)


def _default_vm_name(config: Dict[str, Any]) -> Optional[str]:
    vms_section = config.get("vms")
    if isinstance(vms_section, dict) and vms_section:
        return next(iter(vms_section.keys()))
    return None


def _normalize_agent_type(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(tr("config.agent_type_missing"))

    normalized = ALLOWED_AGENT_TYPES.get(value.strip().lower())
    if normalized is None:
        allowed = ", ".join(sorted({key for key in ALLOWED_AGENT_TYPES if "-" not in key}))
        raise ConfigError(tr("config.agent_type_unknown", value=value, allowed=allowed))
    return normalized


def _normalize_env_vars(value: Any) -> Dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(tr("config.agent_env_not_mapping"))

    normalized: Dict[str, str] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise ConfigError(tr("config.env_name_empty"))
        normalized[str(raw_key)] = "" if raw_value is None else str(raw_value)
    return normalized


def _normalize_default_args(value: Any) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(tr("config.agent_default_args_not_list"))

    normalized: List[str] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            raise ConfigError(tr("config.agent_default_args_empty", index=index))
        normalized.append(entry)
    return normalized


def load_agents_config(config: Dict[str, Any]) -> Dict[str, AgentConfig]:
    raw_agents = config.get("agents") or {}
    if not isinstance(raw_agents, dict):
        raise ConfigError(tr("config.agents_not_mapping"))

    default_vm = _default_vm_name(config)
    agents: Dict[str, AgentConfig] = {}
    for agent_name, raw_entry in raw_agents.items():
        if not isinstance(raw_entry, dict):
            raise ConfigError(tr("config.agent_not_mapping", agent_name=agent_name))

        agent_type = _normalize_agent_type(raw_entry.get("type"))
        env_vars = _normalize_env_vars(raw_entry.get("env"))
        default_args = _normalize_default_args(raw_entry.get("default-args"))
        vm_name = raw_entry.get("vm") or default_vm
        vm_name = str(vm_name) if vm_name else None

        agents[agent_name] = AgentConfig(
            name=str(agent_name),
            type=agent_type,
            env=env_vars,
            default_args=default_args,
            vm_name=vm_name,
        )

    return agents


def _normalize_interval(raw_value: Any) -> int:
    if raw_value is None:
        return 5
    try:
        interval = int(raw_value)
    except (TypeError, ValueError):
        raise ConfigError(tr("config.mount_interval_not_int"))
    if interval <= 0:
        raise ConfigError(tr("config.mount_interval_not_positive"))
    return interval


def _normalize_max_backups(raw_value: Any, index: int) -> int:
    if raw_value is None:
        return 100
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ConfigError(tr("config.mount_max_backups_not_int", index=index))
    if value <= 0:
        raise ConfigError(tr("config.mount_max_backups_not_positive", index=index))
    return value


def _normalize_backup_clean_method(raw_value: Any, index: int) -> str:
    if raw_value is None:
        return "thin"
    if not isinstance(raw_value, str):
        raise ConfigError(tr("config.mount_backup_clean_method_not_string", index=index))
    cleaned = raw_value.strip().lower()
    if cleaned in {"tail", "thin"}:
        return cleaned
    raise ConfigError(tr("config.mount_backup_clean_method_unknown", index=index, value=raw_value))


def load_mounts_config(config: Dict[str, Any]) -> List[MountConfig]:
    raw_mounts = config.get("mounts") or []
    if not isinstance(raw_mounts, list):
        raise ConfigError(tr("config.mounts_not_list"))

    default_vm = _default_vm_name(config)
    if raw_mounts and default_vm is None:
        raise ConfigError(tr("config.mounts_missing_vms"))

    mounts: List[MountConfig] = []
    for index, entry in enumerate(raw_mounts):
        if not isinstance(entry, dict):
            raise ConfigError(tr("config.mount_entry_not_mapping", index=index + 1))

        if "source" not in entry:
            raise ConfigError(tr("config.mount_entry_missing_source", index=index + 1))

        source = _ensure_path(entry.get("source"), f"mounts[{index}].source")
        target_raw = entry.get("target")
        backup_raw = entry.get("backup")
        vm_name = entry.get("vm") or default_vm
        if not vm_name:
            raise ConfigError(tr("config.mount_entry_missing_vm", index=index + 1))

        target = _ensure_path(target_raw, f"mounts[{index}].target") if target_raw else _default_target(source)
        backup = _ensure_path(backup_raw, f"mounts[{index}].backup") if backup_raw else _default_backup(source)
        interval_minutes = _normalize_interval(entry.get("interval"))
        max_backups = _normalize_max_backups(entry.get("max_backups"), index + 1)
        backup_clean_method = _normalize_backup_clean_method(entry.get("backup_clean_method"), index + 1)

        mounts.append(
            MountConfig(
                source=source,
                target=target,
                backup=backup,
                interval_minutes=interval_minutes,
                max_backups=max_backups,
                backup_clean_method=backup_clean_method,
                vm_name=str(vm_name),
            )
        )

    return mounts
