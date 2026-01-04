from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import click
import yaml
from yaml import YAMLError

from . import non_interactive_option
from ..config import ALLOWED_AGENT_TYPES, resolve_config_path


def _prompt_positive_int(message: str, default: int) -> int:
    while True:
        value = click.prompt(message, default=default, type=int)
        if value > 0:
            return value
        click.echo("Значение должно быть больше нуля.")


def _prompt_cloud_init() -> Dict[str, object]:
    path_raw = click.prompt(
        "Путь к файлу cloud-init (оставьте пустым, если конфиг не нужен)",
        default="",
        show_default=False,
    ).strip()
    if not path_raw:
        return {}

    path = Path(path_raw).expanduser()
    if not path.exists():
        click.echo(f"Файл {path} не найден, cloud-init останется пустым.")
        return {}

    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except YAMLError as exc:
        raise click.ClickException(f"Не удалось прочитать cloud-init из {path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise click.ClickException("cloud-init должен быть YAML-объектом (mapping).")

    return loaded


def _prompt_vms() -> Dict[str, Dict[str, object]]:
    click.echo("Настроим виртуальные машины.")
    vms: Dict[str, Dict[str, object]] = {}
    default_name = "agent-ubuntu"

    while True:
        name = click.prompt("Имя ВМ", default=default_name if not vms else f"vm-{len(vms) + 1}")
        cpu = _prompt_positive_int(f"Сколько vCPU выделить для {name}?", default=2)
        ram = click.prompt("Размер RAM (например, 4G)", default="4G")
        disk = click.prompt("Размер диска (например, 20G)", default="20G")
        proxychains = click.prompt(
            "Адрес прокси для proxychains (формат scheme://host:port, оставьте пустым если не нужен)",
            default="",
            show_default=False,
        ).strip()
        cloud_init = _prompt_cloud_init()

        vm_entry: Dict[str, object] = {"cpu": cpu, "ram": ram, "disk": disk, "cloud-init": cloud_init}
        if proxychains:
            vm_entry["proxychains"] = proxychains
        vms[name] = vm_entry

        if not click.confirm("Добавить ещё одну ВМ?", default=False):
            break

    return vms


def _default_mount_name(source: Path) -> str:
    return source.name or "data"


def _prompt_mounts(vm_names: List[str]) -> List[Dict[str, object]]:
    mounts: List[Dict[str, object]] = []
    if not vm_names:
        return mounts

    while click.confirm("Добавить монтирование директорий?", default=not mounts):
        source_raw = click.prompt("Путь к исходной директории (source)", default=str(Path.cwd()))
        source = Path(source_raw).expanduser()
        mount_name = _default_mount_name(source)

        default_target = Path("/home/ubuntu") / mount_name
        target = click.prompt("Папка внутри ВМ (target)", default=str(default_target))

        default_backup = source.parent / f"backups-{mount_name}"
        backup = click.prompt("Каталог для бэкапов", default=str(default_backup))

        interval = _prompt_positive_int("Интервал бэкапа в минутах", default=5)

        vm_choice = click.prompt(
            "Какую ВМ использовать для монтирования?",
            default=vm_names[0],
            type=click.Choice(vm_names),
        )

        mounts.append(
            {
                "source": str(source),
                "target": target,
                "backup": backup,
                "interval": interval,
                "vm": vm_choice,
            }
        )

    return mounts


def _prompt_agents(vm_names: List[str]) -> Dict[str, Dict[str, object]]:
    agents: Dict[str, Dict[str, object]] = {}
    if not vm_names:
        return agents

    agent_type_choices = list(ALLOWED_AGENT_TYPES.keys())

    while click.confirm("Добавить агента для запуска внутри ВМ?", default=False):
        name = click.prompt("Имя агента", default=f"agent{len(agents) + 1}" if agents else "qwen")
        agent_type = click.prompt(
            "Тип агента",
            default="qwen",
            type=click.Choice(agent_type_choices),
        )
        vm_choice = click.prompt(
            "ВМ по умолчанию для агента",
            default=vm_names[0],
            type=click.Choice(vm_names),
        )

        env_vars: Dict[str, str] = {}
        while click.confirm("Добавить переменную окружения для агента?", default=False):
            key = click.prompt("Имя переменной", default="", show_default=False).strip()
            if not key:
                click.echo("Имя переменной не может быть пустым.")
                continue
            value = click.prompt(f"Значение для {key}", default="", show_default=False)
            env_vars[key] = value

        socks5_proxy = click.prompt(
            "socks5_proxy (оставьте пустым, если не нужен)",
            default="",
            show_default=False,
        ).strip()

        agent_entry: Dict[str, object] = {
            "type": agent_type,
            "env": env_vars,
            "vm": vm_choice,
        }
        if socks5_proxy:
            agent_entry["socks5_proxy"] = socks5_proxy

        agents[name] = agent_entry

    return agents


@click.command(name="config-gen")
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help="Куда сохранять YAML-конфиг (по умолчанию ~/.config/agsekit/config.yaml или $CONFIG_PATH).",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Пересоздать конфиг, даже если файл уже существует.",
)
def config_gen_command(config_path: Optional[str], overwrite: bool, non_interactive: bool) -> None:
    """Интерактивно собирает YAML-конфиг agsekit и сохраняет его на диск."""

    del non_interactive
    resolved_default_path = resolve_config_path(Path(config_path) if config_path else None)
    click.echo("Создадим новый конфигурационный файл agsekit.")

    vms = _prompt_vms()
    mounts = _prompt_mounts(list(vms.keys()))
    agents = _prompt_agents(list(vms.keys()))

    destination = Path(
        click.prompt("Куда сохранить конфиг?", default=str(resolved_default_path))
    ).expanduser()

    if destination.exists() and not overwrite:
        click.echo(
            f"Файл конфигурации уже существует: {destination}\n"
            "Отредактируйте его вручную или запустите команду с флагом --overwrite, чтобы пересоздать файл."
        )
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
    click.echo(f"Конфигурация сохранена в {destination}.")
