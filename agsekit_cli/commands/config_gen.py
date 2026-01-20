from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import click
import yaml
from yaml import YAMLError

from . import non_interactive_option
from ..config import ALLOWED_AGENT_TYPES, resolve_config_path
from ..i18n import tr


def _prompt_positive_int(message: str, default: int) -> int:
    while True:
        value = click.prompt(message, default=default, type=int)
        if value > 0:
            return value
        click.echo(tr("config_gen.value_positive"))


def _prompt_cloud_init() -> Dict[str, object]:
    path_raw = click.prompt(
        tr("config_gen.cloud_init_path"),
        default="",
        show_default=False,
    ).strip()
    if not path_raw:
        return {}

    path = Path(path_raw).expanduser()
    if not path.exists():
        click.echo(tr("config_gen.cloud_init_missing", path=path))
        return {}

    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except YAMLError as exc:
        raise click.ClickException(tr("config_gen.cloud_init_read_failed", path=path, error=exc)) from exc

    if not isinstance(loaded, dict):
        raise click.ClickException(tr("config_gen.cloud_init_not_mapping"))

    return loaded


def _prompt_vms() -> Dict[str, Dict[str, object]]:
    click.echo(tr("config_gen.vms_intro"))
    vms: Dict[str, Dict[str, object]] = {}
    default_name = "agent-ubuntu"

    while True:
        name = click.prompt(tr("config_gen.vm_name"), default=default_name if not vms else f"vm-{len(vms) + 1}")
        cpu = _prompt_positive_int(tr("config_gen.vm_cpu", vm_name=name), default=2)
        ram = click.prompt(tr("config_gen.vm_ram"), default="4G")
        disk = click.prompt(tr("config_gen.vm_disk"), default="20G")
        proxychains = click.prompt(
            tr("config_gen.vm_proxychains"),
            default="",
            show_default=False,
        ).strip()
        cloud_init = _prompt_cloud_init()

        vm_entry: Dict[str, object] = {"cpu": cpu, "ram": ram, "disk": disk, "cloud-init": cloud_init}
        if proxychains:
            vm_entry["proxychains"] = proxychains
        vms[name] = vm_entry

        if not click.confirm(tr("config_gen.vm_add_more"), default=False):
            break

    return vms


def _default_mount_name(source: Path) -> str:
    return source.name or "data"


def _prompt_mounts(vm_names: List[str]) -> List[Dict[str, object]]:
    mounts: List[Dict[str, object]] = []
    if not vm_names:
        return mounts

    while click.confirm(tr("config_gen.mount_add"), default=not mounts):
        source_raw = click.prompt(tr("config_gen.mount_source"), default=str(Path.cwd()))
        source = Path(source_raw).expanduser()
        mount_name = _default_mount_name(source)

        default_target = Path("/home/ubuntu") / mount_name
        target = click.prompt(tr("config_gen.mount_target"), default=str(default_target))

        default_backup = source.parent / f"backups-{mount_name}"
        backup = click.prompt(tr("config_gen.mount_backup"), default=str(default_backup))

        interval = _prompt_positive_int(tr("config_gen.mount_interval"), default=5)
        max_backups = _prompt_positive_int(tr("config_gen.mount_max_backups"), default=100)
        backup_clean_method = click.prompt(
            tr("config_gen.mount_backup_clean_method"),
            default="thin",
            type=click.Choice(["tail", "thin"], case_sensitive=False),
        )

        vm_choice = click.prompt(
            tr("config_gen.mount_vm"),
            default=vm_names[0],
            type=click.Choice(vm_names),
        )

        mounts.append(
            {
                "source": str(source),
                "target": target,
                "backup": backup,
                "interval": interval,
                "max_backups": max_backups,
                "backup_clean_method": backup_clean_method,
                "vm": vm_choice,
            }
        )

    return mounts


def _prompt_agents(vm_names: List[str]) -> Dict[str, Dict[str, object]]:
    agents: Dict[str, Dict[str, object]] = {}
    if not vm_names:
        return agents

    agent_type_choices = list(ALLOWED_AGENT_TYPES.keys())

    while click.confirm(tr("config_gen.agent_add"), default=False):
        name = click.prompt(tr("config_gen.agent_name"), default=f"agent{len(agents) + 1}" if agents else "qwen")
        agent_type = click.prompt(
            tr("config_gen.agent_type"),
            default="qwen",
            type=click.Choice(agent_type_choices),
        )
        vm_choice = click.prompt(
            tr("config_gen.agent_vm"),
            default=vm_names[0],
            type=click.Choice(vm_names),
        )

        env_vars: Dict[str, str] = {}
        while click.confirm(tr("config_gen.agent_env_add"), default=False):
            key = click.prompt(tr("config_gen.agent_env_key"), default="", show_default=False).strip()
            if not key:
                click.echo(tr("config_gen.agent_env_key_empty"))
                continue
            value = click.prompt(tr("config_gen.agent_env_value", key=key), default="", show_default=False)
            env_vars[key] = value

        agent_entry: Dict[str, object] = {
            "type": agent_type,
            "env": env_vars,
            "vm": vm_choice,
        }
        agents[name] = agent_entry

    return agents


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
    """Интерактивно собирает YAML-конфиг agsekit и сохраняет его на диск."""

    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive
    resolved_default_path = resolve_config_path(Path(config_path) if config_path else None)
    click.echo(tr("config_gen.start"))

    vms = _prompt_vms()
    mounts = _prompt_mounts(list(vms.keys()))
    agents = _prompt_agents(list(vms.keys()))

    destination = Path(click.prompt(tr("config_gen.destination_prompt"), default=str(resolved_default_path))).expanduser()

    if destination.exists() and not overwrite:
        click.echo(tr("config_gen.destination_exists", path=destination))
        return

    destination.parent.mkdir(parents=True, exist_ok=True)

    config_data: Dict[str, object] = {"vms": vms}
    if mounts:
        config_data["mounts"] = mounts
    if agents:
        config_data["agents"] = agents

    destination.write_text(
        yaml.safe_dump(config_data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    click.echo(tr("config_gen.saved", path=destination))
