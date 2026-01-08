from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import yaml

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


@dataclass
class AgentConfig:
    name: str
    type: str
    env: Dict[str, str]
    default_args: List[str]
    socks5_proxy: Optional[str]
    vm_name: Optional[str]


class ConfigError(RuntimeError):
    """Raised when configuration cannot be loaded."""


def resolve_config_path(explicit_path: Optional[Path] = None) -> Path:
    env_path = os.environ.get(CONFIG_ENV_VAR)
    base_path = explicit_path or (Path(env_path) if env_path else DEFAULT_CONFIG_PATH)
    return base_path.expanduser()


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
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


def _normalize_address(value: Any, field_name: str) -> str:
    if not isinstance(value, (str, int, float)):
        raise ConfigError(f"{field_name} must be a host:port string")

    text = str(value).strip()
    if ":" not in text:
        raise ConfigError(f"{field_name} must include host and port separated by colon")

    host, port_text = text.rsplit(":", 1)
    if not host:
        raise ConfigError(f"{field_name} must include host before port")
    try:
        port = int(port_text)
    except ValueError:
        raise ConfigError(f"{field_name} must contain a numeric port")
    if port <= 0 or port > 65535:
        raise ConfigError(f"{field_name} must contain a valid TCP port")

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
        raise ConfigError(f"vms.{vm_name}.port-forwarding must be a list")

    rules: List[PortForwardingRule] = []
    for index, rule in enumerate(raw_entry):
        if not isinstance(rule, dict):
            raise ConfigError(f"vms.{vm_name}.port-forwarding[{index}] must be a mapping")

        raw_type = rule.get("type")
        if raw_type not in {"local", "remote", "socks5"}:
            raise ConfigError(
                f"vms.{vm_name}.port-forwarding[{index}].type must be one of: local, remote, socks5"
            )

        vm_addr_raw = rule.get("vm-addr")
        if vm_addr_raw is None:
            raise ConfigError(f"vms.{vm_name}.port-forwarding[{index}] is missing vm-addr")

        host_addr: Optional[str]
        if raw_type in {"local", "remote"}:
            host_addr_raw = rule.get("host-addr")
            if host_addr_raw is None:
                raise ConfigError(f"vms.{vm_name}.port-forwarding[{index}] is missing host-addr")
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
        raise ConfigError(f"vms.{vm_name}.proxychains must be a string")
    cleaned = value.strip()
    if not cleaned:
        return None

    parsed = urlparse(cleaned)
    if not parsed.scheme or not parsed.hostname or not parsed.port:
        raise ConfigError(
            f"vms.{vm_name}.proxychains must be a proxy URL in the form scheme://host:port (e.g. socks5://127.0.0.1:8080)"
        )
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ConfigError(f"vms.{vm_name}.proxychains must not include credentials, paths, or query parameters")

    scheme = parsed.scheme.lower()
    allowed_schemes = {"http", "https", "socks4", "socks5"}
    if scheme not in allowed_schemes:
        raise ConfigError(
            f"vms.{vm_name}.proxychains must use one of the supported schemes: {', '.join(sorted(allowed_schemes))}"
        )

    return f"{scheme}://{parsed.hostname}:{parsed.port}"


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
            port_forwarding=_normalize_port_forwarding(raw_entry.get("port-forwarding"), vm_name),
            proxychains=_normalize_proxychains(raw_entry.get("proxychains"), vm_name),
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


def _normalize_agent_type(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("Agent `type` must be a non-empty string")

    normalized = ALLOWED_AGENT_TYPES.get(value.strip().lower())
    if normalized is None:
        allowed = ", ".join(sorted({key for key in ALLOWED_AGENT_TYPES if "-" not in key}))
        raise ConfigError(f"Unknown agent type: {value}. Supported types: {allowed}")
    return normalized


def _normalize_env_vars(value: Any) -> Dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("Agent `env` must be a mapping of variable names to values")

    normalized: Dict[str, str] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise ConfigError("Environment variable names must be non-empty strings")
        normalized[str(raw_key)] = "" if raw_value is None else str(raw_value)
    return normalized


def _normalize_default_args(value: Any) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError("Agent `default-args` must be a list of strings")

    normalized: List[str] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            raise ConfigError(f"Agent `default-args[{index}]` must be a non-empty string")
        normalized.append(entry)
    return normalized


def load_agents_config(config: Dict[str, Any]) -> Dict[str, AgentConfig]:
    raw_agents = config.get("agents") or {}
    if not isinstance(raw_agents, dict):
        raise ConfigError("Config `agents` must be a mapping")

    default_vm = _default_vm_name(config)
    agents: Dict[str, AgentConfig] = {}
    for agent_name, raw_entry in raw_agents.items():
        if not isinstance(raw_entry, dict):
            raise ConfigError(f"Agent `{agent_name}` must be a mapping of its parameters")

        agent_type = _normalize_agent_type(raw_entry.get("type"))
        env_vars = _normalize_env_vars(raw_entry.get("env"))
        default_args = _normalize_default_args(raw_entry.get("default-args"))
        socks5_proxy = raw_entry.get("socks5_proxy")
        if socks5_proxy is not None and (not isinstance(socks5_proxy, str) or not socks5_proxy.strip()):
            raise ConfigError(f"Agent `{agent_name}` socks5_proxy must be a non-empty string if provided")

        vm_name = raw_entry.get("vm") or default_vm
        vm_name = str(vm_name) if vm_name else None

        agents[agent_name] = AgentConfig(
            name=str(agent_name),
            type=agent_type,
            env=env_vars,
            default_args=default_args,
            socks5_proxy=str(socks5_proxy) if socks5_proxy else None,
            vm_name=vm_name,
        )

    return agents


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
