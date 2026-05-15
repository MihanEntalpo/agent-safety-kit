from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import click
import questionary
import yaml

from . import non_interactive_option
from ..agents_modules import SUPPORTED_AGENT_TYPES
from ..config import (
    DEFAULT_HTTP_PROXY_PORT_POOL_END,
    DEFAULT_HTTP_PROXY_PORT_POOL_START,
    DEFAULT_PORTFORWARD_CONFIG_CHECK_INTERVAL_SEC,
    DEFAULT_STATE_FILE_PATH,
    DEFAULT_VERSION_CHECK_INTERVAL_SEC,
    agent_runtime_binary,
    default_agent_version,
    resolve_config_path,
)
from ..interactive import is_interactive_terminal
from ..i18n import tr
from ..tui_prompts import (
    DEFAULT_BACKUPIGNORE_LINES,
    NO_RESTRICTIONS_VALUE,
    ask_checkbox,
    ask_choice,
    ask_confirm,
    ask_path,
    ask_select,
    ask_text,
    make_positive_int_validator,
    make_required_validator,
    parse_positive_int,
    require_non_empty_selection,
)
from ..vm_bundle_definitions import BUNDLE_DEFINITIONS

_PROXY_SCHEMES = {"http", "https", "socks4", "socks5"}


def _validate_positive_int(value: str) -> object:
    return make_positive_int_validator(
        tr("config_gen.value_required"),
        tr("config_gen.value_positive"),
    )(value)


def _parse_positive_int(value: str) -> int:
    return parse_positive_int(value)


def _validate_non_empty(value: str) -> object:
    return make_required_validator(tr("config_gen.value_required"))(value)


def _validate_proxy_url_optional(value: str) -> object:
    text = str(value).strip()
    if not text or text == '""':
        return True
    return _validate_proxy_url_required(text)


def _validate_proxy_url_required(value: str) -> object:
    text = str(value).strip()
    if not text:
        return tr("config_gen.value_required")
    parsed = urlparse(text)
    if parsed.scheme not in _PROXY_SCHEMES:
        return tr("config_gen.proxy_url_invalid")
    if not parsed.hostname or parsed.port is None:
        return tr("config_gen.proxy_url_invalid")
    if parsed.username or parsed.password:
        return tr("config_gen.proxy_url_invalid")
    if parsed.path not in {"", "/"}:
        return tr("config_gen.proxy_url_invalid")
    if parsed.params or parsed.query or parsed.fragment:
        return tr("config_gen.proxy_url_invalid")
    return True


def _validate_host_port(value: str) -> object:
    text = str(value).strip()
    if not text:
        return tr("config_gen.value_required")
    if ":" not in text:
        return tr("config_gen.host_port_invalid")
    host, port_text = text.rsplit(":", 1)
    if not host:
        return tr("config_gen.host_port_invalid")
    try:
        port = int(port_text)
    except ValueError:
        return tr("config_gen.host_port_invalid")
    if port <= 0 or port > 65535:
        return tr("config_gen.host_port_invalid")
    return True


def _prompt_positive_int(message: str, default: int) -> int:
    return _parse_positive_int(ask_text(message, default=str(default), validate=_validate_positive_int))


def _prompt_optional_path(message: str, *, default: str = "") -> Optional[str]:
    value = ask_path(message, default=default)
    if not value:
        return None
    return str(Path(value).expanduser())


def _prompt_optional_proxy(message: str) -> Optional[str]:
    value = ask_text(message, default="", validate=_validate_proxy_url_optional)
    if not value:
        return None
    return value


def _prompt_override_proxy(message: str) -> tuple[bool, Optional[str]]:
    value = ask_text(message, default="", validate=_validate_proxy_url_optional)
    if not value:
        return False, None
    if value == '""':
        return True, ""
    return True, value


def _prompt_bundle_selection() -> List[str]:
    choices = [questionary.Choice(name, value=name) for name in BUNDLE_DEFINITIONS]
    selected = ask_checkbox(
        tr("config_gen.vm_install"),
        choices=choices,
        instruction=tr("config_gen.checkbox_instruction_optional"),
    )
    return [str(item) for item in selected]


def _prompt_port_forwarding() -> Optional[List[Dict[str, str]]]:
    if not ask_confirm(tr("config_gen.vm_port_forwarding_enable"), default=False):
        return None

    rules: List[Dict[str, str]] = []
    while True:
        selected = ask_choice(
            tr("config_gen.vm_port_forwarding_type"),
            choices=["local", "remote", "socks5", tr("config_gen.cancel")],
            default="local",
        )
        if selected == tr("config_gen.cancel"):
            return rules or None

        vm_addr = ask_text(tr("config_gen.vm_port_forwarding_vm_addr"), default="", validate=_validate_host_port)
        if selected == "socks5":
            rules.append({"type": "socks5", "vm-addr": vm_addr})
        else:
            host_addr = ask_text(tr("config_gen.vm_port_forwarding_host_addr"), default="", validate=_validate_host_port)
            rules.append({"type": str(selected), "host-addr": host_addr, "vm-addr": vm_addr})

        if not ask_confirm(tr("config_gen.vm_port_forwarding_add_more"), default=False):
            return rules


def _next_available_name(base_name: str, existing_names: List[str]) -> str:
    if base_name not in existing_names:
        return base_name
    suffix = 2
    while f"{base_name}-{suffix}" in existing_names:
        suffix += 1
    return f"{base_name}-{suffix}"


def _prompt_unique_name(
    message: str,
    *,
    default_name: str,
    existing_names: List[str],
    taken_message_key: str,
) -> str:
    while True:
        value = ask_text(message, default=default_name, validate=_validate_non_empty)
        if value not in existing_names:
            return value
        click.echo(tr(taken_message_key, name=value))


def _prompt_vms() -> Dict[str, Dict[str, object]]:
    click.echo(tr("config_gen.vms_intro"))

    vms: Dict[str, Dict[str, object]] = {}
    while True:
        default_name = _next_available_name("agent-ubuntu", list(vms.keys()))
        name = _prompt_unique_name(
            tr("config_gen.vm_name"),
            default_name=default_name,
            existing_names=list(vms.keys()),
            taken_message_key="config_gen.vm_name_taken",
        )
        cpu = _prompt_positive_int(tr("config_gen.vm_cpu", vm_name=name), default=2)
        ram = ask_text(tr("config_gen.vm_ram"), default="4G", validate=_validate_non_empty)
        disk = ask_text(tr("config_gen.vm_disk"), default="20G", validate=_validate_non_empty)
        install = _prompt_bundle_selection()
        proxychains = _prompt_optional_proxy(tr("config_gen.vm_proxychains"))
        http_proxy = _prompt_optional_proxy(tr("config_gen.vm_http_proxy"))
        port_forwarding = _prompt_port_forwarding()

        vm_entry: Dict[str, object] = {
            "cpu": cpu,
            "ram": ram,
            "disk": disk,
        }
        if install:
            vm_entry["install"] = install
        if proxychains:
            vm_entry["proxychains"] = proxychains
        if http_proxy:
            vm_entry["http_proxy"] = http_proxy
        if port_forwarding:
            vm_entry["port-forwarding"] = port_forwarding
        vms[name] = vm_entry

        if not ask_confirm(tr("config_gen.vm_add_more"), default=False):
            break

    return vms


def _default_agent_name(agent_type: str) -> str:
    if agent_type in {"codex-glibc", "codex-glibc-prebuilt"}:
        return "codex"
    return agent_runtime_binary(agent_type)


def _prompt_env_vars() -> Dict[str, str]:
    env_vars: Dict[str, str] = {}
    while True:
        raw = ask_text(tr("config_gen.agent_env_line"), default="")
        if not raw:
            break
        if "=" not in raw:
            click.echo(tr("config_gen.agent_env_invalid"))
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            click.echo(tr("config_gen.agent_env_invalid"))
            continue
        env_vars[key] = value
    return env_vars


def _prompt_default_args() -> List[str]:
    raw = ask_text(tr("config_gen.agent_default_args_line"), default="")
    if not raw:
        return []
    return raw.split()


def _prompt_agent_version(agent_type: str) -> str:
    default_version = default_agent_version(agent_type)
    value = ask_text(
        tr("config_gen.agent_version"),
        default=default_version,
        validate=lambda _value: True,
    )
    return value or default_version


def _validate_non_empty_selection(values: List[object]) -> object:
    return require_non_empty_selection(values, tr("config_gen.select_at_least_one"))


def _prompt_agent_vms(vm_names: List[str]) -> List[str]:
    choices = [questionary.Choice(name, value=name, checked=True) for name in vm_names]
    selected = ask_checkbox(
        tr("config_gen.agent_vms"),
        choices=choices,
        validate=_validate_non_empty_selection,
        instruction=tr("config_gen.checkbox_instruction_required"),
    )
    return [str(item) for item in selected]


def _prompt_agents(vm_names: List[str]) -> Dict[str, Dict[str, object]]:
    click.echo(tr("config_gen.agents_intro"))

    agents: Dict[str, Dict[str, object]] = {}
    while True:
        selected_type = ask_select(
            tr("config_gen.agent_type"),
            choices=[
                *[questionary.Choice(agent_type, value=agent_type) for agent_type in SUPPORTED_AGENT_TYPES],
                questionary.Choice(tr("config_gen.cancel"), value=tr("config_gen.cancel")),
            ],
        )
        if selected_type == tr("config_gen.cancel"):
            return agents

        agent_type = str(selected_type)
        default_name = _next_available_name(_default_agent_name(agent_type), list(agents.keys()))
        name = _prompt_unique_name(
            tr("config_gen.agent_name"),
            default_name=default_name,
            existing_names=list(agents.keys()),
            taken_message_key="config_gen.agent_name_taken",
        )
        version = _prompt_agent_version(agent_type)
        env_vars: Dict[str, str] = {}
        if ask_confirm(tr("config_gen.agent_env_enable"), default=False):
            env_vars = _prompt_env_vars()
        default_args: List[str] = []
        if ask_confirm(tr("config_gen.agent_default_args_enable"), default=False):
            default_args = _prompt_default_args()

        assigned_vms: Optional[List[str]] = None
        if len(vm_names) > 1:
            assigned_vms = _prompt_agent_vms(vm_names)

        proxychains_defined, proxychains_value = _prompt_override_proxy(tr("config_gen.agent_proxychains"))
        http_proxy_defined, http_proxy_value = _prompt_override_proxy(tr("config_gen.agent_http_proxy"))

        agent_entry: Dict[str, object] = {"type": agent_type, "version": version}
        if env_vars:
            agent_entry["env"] = env_vars
        if default_args:
            agent_entry["default-args"] = default_args
        if assigned_vms is not None:
            agent_entry["vms"] = assigned_vms
        if proxychains_defined:
            agent_entry["proxychains"] = proxychains_value
        if http_proxy_defined:
            agent_entry["http_proxy"] = http_proxy_value
        agents[name] = agent_entry

        if not ask_confirm(tr("config_gen.agent_add_more"), default=False):
            break

    return agents


def _default_mount_name(source: Path) -> str:
    return source.name or "data"


def _validate_mount_allowed_agents(values: List[object]) -> object:
    if not values:
        return tr("config_gen.select_at_least_one")
    if NO_RESTRICTIONS_VALUE in values and len(values) > 1:
        return tr("config_gen.mount_allowed_agents_conflict")
    return True


def _create_default_backupignore(source: Path) -> None:
    ignore_path = source / ".backupignore"
    if ignore_path.exists():
        click.echo(tr("config_gen.backupignore_exists", path=ignore_path))
        return
    source.mkdir(parents=True, exist_ok=True)
    ignore_path.write_text("\n".join(DEFAULT_BACKUPIGNORE_LINES) + "\n", encoding="utf-8")
    click.echo(tr("config_gen.backupignore_created", path=ignore_path))


def _prompt_mount_allowed_agents(agent_names: List[str]) -> Optional[List[str]]:
    if not agent_names:
        return None

    choices: List[object] = [questionary.Choice(tr("config_gen.no_restrictions"), value=NO_RESTRICTIONS_VALUE, checked=True)]
    choices.extend(questionary.Choice(name, value=name) for name in agent_names)
    selected = ask_checkbox(
        tr("config_gen.mount_allowed_agents"),
        choices=choices,
        validate=_validate_mount_allowed_agents,
        instruction=tr("config_gen.checkbox_instruction_optional"),
    )
    if NO_RESTRICTIONS_VALUE in selected:
        return None
    return [str(item) for item in selected]


def _prompt_mounts(vm_names: List[str], agent_names: List[str]) -> List[Dict[str, object]]:
    mounts: List[Dict[str, object]] = []
    if not ask_confirm(tr("config_gen.mounts_enable"), default=False):
        return mounts

    while True:
        source_raw = ask_path(tr("config_gen.mount_source"), default="", validate=_validate_non_empty)
        source = Path(source_raw).expanduser()
        mount_name = _default_mount_name(source)
        target = ask_text(tr("config_gen.mount_target"), default=f"/home/ubuntu/{mount_name}", validate=_validate_non_empty)
        default_backup = source.parent / f"backups-{mount_name}"
        backup = ask_path(tr("config_gen.mount_backup"), default=str(default_backup))

        vm_name = vm_names[0]
        if len(vm_names) > 1:
            vm_name = ask_choice(tr("config_gen.mount_vm"), choices=vm_names, default=vm_names[0])

        allowed_agents = _prompt_mount_allowed_agents(agent_names)

        if ask_confirm(tr("config_gen.mount_backupignore_create"), default=True):
            _create_default_backupignore(source)

        mount_entry: Dict[str, object] = {
            "source": str(source),
            "target": target,
            "backup": backup,
            "vm": vm_name,
        }
        if allowed_agents is not None:
            mount_entry["allowed_agents"] = allowed_agents
        mounts.append(mount_entry)

        if not ask_confirm(tr("config_gen.mount_add_more"), default=False):
            break

    return mounts


def _prompt_global() -> Dict[str, object]:
    click.echo(tr("config_gen.global_intro"))

    global_config: Dict[str, object] = {}
    ssh_keys_folder = _prompt_optional_path(tr("config_gen.global_ssh_keys_folder"))
    systemd_env_folder = _prompt_optional_path(tr("config_gen.global_systemd_env_folder"))
    state_file = _prompt_optional_path(
        tr("config_gen.global_state_file"),
        default=str(DEFAULT_STATE_FILE_PATH),
    )
    if ssh_keys_folder:
        global_config["ssh_keys_folder"] = ssh_keys_folder
    if systemd_env_folder:
        global_config["systemd_env_folder"] = systemd_env_folder
    if state_file and Path(state_file).expanduser() != DEFAULT_STATE_FILE_PATH:
        global_config["state_file"] = state_file

    global_config["portforward_config_check_interval_sec"] = _prompt_positive_int(
        tr("config_gen.global_portforward_interval"),
        default=DEFAULT_PORTFORWARD_CONFIG_CHECK_INTERVAL_SEC,
    )
    global_config["check_new_version"] = ask_confirm(
        tr("config_gen.global_check_new_version"),
        default=True,
    )
    global_config["check_new_version_interval_sec"] = _prompt_positive_int(
        tr("config_gen.global_check_new_version_interval"),
        default=DEFAULT_VERSION_CHECK_INTERVAL_SEC,
    )
    global_config["http_proxy_port_pool"] = {
        "start": _prompt_positive_int(
            tr("config_gen.global_http_proxy_port_pool_start"),
            default=DEFAULT_HTTP_PROXY_PORT_POOL_START,
        ),
        "end": _prompt_positive_int(
            tr("config_gen.global_http_proxy_port_pool_end"),
            default=DEFAULT_HTTP_PROXY_PORT_POOL_END,
        ),
    }
    return global_config


def _apply_vm_allowed_agents(vms: Dict[str, Dict[str, object]], agents: Dict[str, Dict[str, object]]) -> None:
    if len(vms) <= 1 or not agents:
        return

    allowed_by_vm: Dict[str, List[str]] = {name: [] for name in vms}
    for agent_name, agent_entry in agents.items():
        assigned_vms = agent_entry.get("vms")
        if not isinstance(assigned_vms, list):
            continue
        for vm_name in assigned_vms:
            if vm_name in allowed_by_vm and agent_name not in allowed_by_vm[vm_name]:
                allowed_by_vm[vm_name].append(agent_name)

    for vm_name, names in allowed_by_vm.items():
        if names:
            vms[vm_name]["allowed_agents"] = names


@click.command(name="config-gen", help=tr("config_gen.command_help"))
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config_gen.option_config_path"),
)
@click.option(
    "--overwrite",
    is_flag=True,
    help=tr("config_gen.option_overwrite"),
)
def config_gen_command(config_path: Optional[str], overwrite: bool, non_interactive: bool) -> None:
    """Interactively collect an agsekit YAML config and save it to disk."""

    if non_interactive or not is_interactive_terminal():
        raise click.ClickException(tr("config_gen.interactive_required"))

    resolved_default_path = resolve_config_path(Path(config_path) if config_path else None)
    click.echo(tr("config_gen.start"))

    vms = _prompt_vms()
    agents = _prompt_agents(list(vms.keys()))
    _apply_vm_allowed_agents(vms, agents)
    mounts = _prompt_mounts(list(vms.keys()), list(agents.keys()))
    global_config: Optional[Dict[str, object]] = None
    if ask_confirm(tr("config_gen.global_customize"), default=False):
        global_config = _prompt_global()

    destination = Path(ask_path(tr("config_gen.destination_prompt"), default=str(resolved_default_path))).expanduser()
    if destination.exists() and not overwrite:
        click.echo(tr("config_gen.destination_exists", path=destination))
        return

    destination.parent.mkdir(parents=True, exist_ok=True)

    config_data: Dict[str, object] = {}
    if global_config:
        config_data["global"] = global_config
    config_data["vms"] = vms
    if mounts:
        config_data["mounts"] = mounts
    if agents:
        config_data["agents"] = agents

    destination.write_text(
        yaml.safe_dump(config_data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    click.echo(tr("config_gen.saved", path=destination))
