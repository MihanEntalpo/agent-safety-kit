from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Union

import click
import questionary

from .agents import AgentConfig
from .config import (
    ConfigError,
    load_agents_config,
    load_config,
    load_mounts_config,
    load_vms_config,
    resolve_config_path,
)
from .mounts import MountConfig

CommandBuilder = Callable[["InteractiveSession"], List[str]]


def is_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


class InteractiveSession:
    def __init__(self, default_config_path: Optional[Path] = None) -> None:
        self.config_path = resolve_config_path(default_config_path)
        self._config_cache: Optional[Dict[str, object]] = None

    def _prompt_config_path(self) -> Path:
        path = questionary.path(
            "Путь к YAML-конфигурации:",
            default=str(self.config_path),
            only_directories=False,
        ).ask()
        if path is None:
            raise click.Abort()
        resolved = Path(path).expanduser()
        self.config_path = resolved
        return resolved

    def _load_config(self) -> Dict[str, object]:
        while True:
            if self._config_cache is not None:
                return self._config_cache

            candidate_path = self._prompt_config_path()
            try:
                self._config_cache = load_config(candidate_path)
                return self._config_cache
            except ConfigError as exc:
                click.echo(f"Не удалось загрузить конфиг: {exc}")
                self._config_cache = None

    def _load_from_config(
        self, loader: Callable[[Dict[str, object]], Union[Dict[str, object], List[object]]], description: str
    ) -> Union[Dict[str, object], List[object]]:
        while True:
            config = self._load_config()
            try:
                return loader(config)
            except ConfigError as exc:
                click.echo(f"Ошибка в разделе конфигурации ({description}): {exc}")
                self._config_cache = None

    def load_mounts(self) -> List[MountConfig]:
        mounts = self._load_from_config(load_mounts_config, "mounts")
        assert isinstance(mounts, list)
        return mounts

    def load_vms(self) -> Dict[str, object]:
        vms = self._load_from_config(load_vms_config, "vms")
        assert isinstance(vms, dict)
        return vms

    def load_agents(self) -> Dict[str, AgentConfig]:
        agents = self._load_from_config(load_agents_config, "agents")
        assert isinstance(agents, dict)
        return agents

    def config_option(self) -> list[str]:
        return ["--config", str(self.config_path)]


def _collect_excludes() -> list[str]:
    excludes: list[str] = []
    while questionary.confirm("Добавить паттерн --exclude?", default=False).ask():
        value = questionary.text("Паттерн исключений rsync:").ask()
        if value:
            excludes.append(value)
    return excludes


def _select_directory(message: str) -> Path:
    path = questionary.path(message, only_directories=True, default=str(Path.cwd())).ask()
    if path is None:
        raise click.Abort()
    return Path(path).expanduser()


def _select_from_list(message: str, choices: Sequence[questionary.QuestionChoice]) -> object:
    answer = questionary.select(message, choices=choices, use_shortcuts=True).ask()
    if answer is None:
        raise click.Abort()
    return answer


def build_backup_once(session: InteractiveSession) -> List[str]:
    source_dir = _select_directory("Исходная директория для бэкапа:")
    dest_dir = _select_directory("Каталог для сохранения снапшотов:")
    excludes = _collect_excludes()

    args = ["backup-once", "--source-dir", str(source_dir), "--dest-dir", str(dest_dir)]
    for pattern in excludes:
        args.extend(["--exclude", pattern])
    return args


def build_backup_repeated(session: InteractiveSession) -> List[str]:
    source_dir = _select_directory("Исходная директория для циклического бэкапа:")
    dest_dir = _select_directory("Каталог для сохранения снапшотов:")
    interval_raw = questionary.text("Интервал в минутах между бэкапами:", default="5").ask()
    if interval_raw is None:
        raise click.Abort()
    excludes = _collect_excludes()

    args = [
        "backup-repeated",
        "--source-dir",
        str(source_dir),
        "--dest-dir",
        str(dest_dir),
        "--interval",
        interval_raw.strip() or "5",
    ]
    for pattern in excludes:
        args.extend(["--exclude", pattern])
    return args


def build_backup_repeated_mount(session: InteractiveSession) -> List[str]:
    mounts = session.load_mounts()
    if not mounts:
        raise click.ClickException("В конфигурации не найдено монтирований.")

    choices = [
        questionary.Choice(f"{mount.source} -> {mount.vm_name}:{mount.target}", value=mount)
        for mount in mounts
    ]
    selected: MountConfig = _select_from_list("Какое монтирование бэкапить?", choices)
    return ["backup-repeated-mount", "--mount", str(selected.source), *session.config_option()]


def build_backup_repeated_all(session: InteractiveSession) -> List[str]:
    session.load_mounts()
    return ["backup-repeated-all", *session.config_option()]


def build_create_vm(session: InteractiveSession) -> List[str]:
    vms = session.load_vms()
    vm_choices = [questionary.Choice(name=name, value=name) for name in vms]
    vm_choices.append(questionary.Choice("Ввести имя вручную", value=None))
    vm_name = _select_from_list("Выберите ВМ для создания:", vm_choices)
    if vm_name is None:
        manual = questionary.text("Имя ВМ:").ask()
        if not manual:
            raise click.Abort()
        vm_name = manual
    return ["create-vm", str(vm_name), *session.config_option()]


def build_create_vms(session: InteractiveSession) -> List[str]:
    session.load_vms()
    return ["create-vms", *session.config_option()]


def _select_mount_choice(session: InteractiveSession, action: str) -> List[str]:
    mounts = session.load_mounts()
    if not mounts:
        raise click.ClickException("В конфигурации не найдено монтирований.")

    all_choice = questionary.Choice("Все папки из конфигурации", value="__all__")
    choices: list[questionary.QuestionChoice] = [all_choice]
    for mount in mounts:
        label = f"{mount.source} -> {mount.vm_name}:{mount.target}"
        choices.append(questionary.Choice(label, value=mount))

    selection = _select_from_list(f"Что нужно {action}?", choices)
    if selection == "__all__":
        return [f"--all"]
    assert isinstance(selection, MountConfig)
    return ["--source-dir", str(selection.source)]


def build_mount(session: InteractiveSession) -> List[str]:
    selection = _select_mount_choice(session, "смонтировать")
    return ["mount", *selection, *session.config_option()]


def build_umount(session: InteractiveSession) -> List[str]:
    selection = _select_mount_choice(session, "отмонтировать")
    return ["umount", *selection, *session.config_option()]


def build_install_agents(session: InteractiveSession) -> List[str]:
    agents = session.load_agents()
    if not agents:
        raise click.ClickException("Агенты в конфигурации не найдены.")
    vms = session.load_vms()

    agent_choices: list[questionary.QuestionChoice] = [questionary.Choice("Все агенты", value="__all__")]
    agent_choices.extend(questionary.Choice(name, value=name) for name in agents)
    agent_choice = _select_from_list("Какого агента установить?", agent_choices)

    default_vm = next(iter(vms.keys())) if vms else None
    default_vm_label = "Использовать ВМ по умолчанию"
    if default_vm:
        default_vm_label += f" ({default_vm})"

    vm_choices: list[questionary.QuestionChoice] = [questionary.Choice(default_vm_label, value="__default__")]
    vm_choices.extend(questionary.Choice(name, value=name) for name in vms)
    vm_choices.append(questionary.Choice("Все виртуалки", value="__all_vms__"))
    vm_choice = _select_from_list("Куда устанавливать агента?", vm_choices)

    args = ["install-agents", *session.config_option()]
    if agent_choice == "__all__":
        args.append("--all-agents")
    else:
        args.append(str(agent_choice))

    if vm_choice == "__all_vms__":
        args.append("--all-vms")
    elif vm_choice and vm_choice != "__default__":
        args.append(str(vm_choice))

    return args


def build_run(session: InteractiveSession) -> List[str]:
    agents = session.load_agents()
    if not agents:
        raise click.ClickException("Агенты в конфигурации не найдены.")
    mounts = session.load_mounts()
    vms = session.load_vms()

    agent_choices = [questionary.Choice(name, value=agent) for name, agent in agents.items()]
    agent: AgentConfig = _select_from_list("Какого агента запустить?", agent_choices)

    mount_choices: list[questionary.QuestionChoice] = [
        questionary.Choice("Не выбирать директорию", value=None),
    ]
    mount_choices.extend(
        questionary.Choice(f"{mount.source} -> {mount.vm_name}:{mount.target}", value=mount) for mount in mounts
    )
    mount_choices.append(questionary.Choice("Указать путь вручную", value="__custom__"))
    mount_choice = _select_from_list("Какую директорию использовать?", mount_choices)

    source_dir: Optional[Path] = None
    if isinstance(mount_choice, MountConfig):
        source_dir = mount_choice.source
    elif mount_choice == "__custom__":
        source_dir = _select_directory("Путь к директории:")

    auto_vm_value = "__auto_vm__"
    vm_choices: list[questionary.QuestionChoice] = [
        questionary.Choice("Определить автоматически", value=auto_vm_value)
    ]
    vm_choices.extend(questionary.Choice(name, value=name) for name in vms)
    vm_choice = _select_from_list("Какую ВМ использовать?", vm_choices)

    if vm_choice == auto_vm_value:
        vm_choice = None

    disable_backups = questionary.confirm("Отключить фоновые бэкапы?", default=False).ask()
    if disable_backups is None:
        raise click.Abort()

    agent_args_raw = questionary.text("Дополнительные аргументы для агента (через пробел):", default="").ask()
    if agent_args_raw is None:
        raise click.Abort()
    agent_args = shlex.split(agent_args_raw)

    args = ["run", agent.name]
    if source_dir:
        args.append(str(source_dir))
    if vm_choice:
        args.extend(["--vm", vm_choice])
    args.extend(session.config_option())
    if disable_backups:
        args.append("--disable-backups")
    args.extend(agent_args)
    return args


def build_config_gen(_: InteractiveSession) -> List[str]:
    return ["config-gen"]


def build_prepare(_: InteractiveSession) -> List[str]:
    return ["prepare"]


def build_shell(session: InteractiveSession) -> List[str]:
    vms = session.load_vms()
    if not vms:
        raise click.ClickException("В конфигурации не найдено ВМ.")

    choices = [questionary.Choice(name, value=name) for name in vms]
    vm_name = _select_from_list("В какую ВМ зайти?", choices)
    return ["shell", str(vm_name), *session.config_option()]


def build_ssh(session: InteractiveSession) -> List[str]:
    vms = session.load_vms()
    if not vms:
        raise click.ClickException("В конфигурации не найдено ВМ.")

    choices = [questionary.Choice(name, value=name) for name in vms]
    vm_name = _select_from_list("В какую ВМ подключиться по SSH?", choices)

    ssh_args_raw = questionary.text("Дополнительные аргументы ssh (через пробел):", default="").ask()
    if ssh_args_raw is None:
        raise click.Abort()
    ssh_args = shlex.split(ssh_args_raw)
    return ["ssh", str(vm_name), *session.config_option(), *ssh_args]


def build_portforward(session: InteractiveSession) -> List[str]:
    session.load_vms()
    return ["portforward", *session.config_option()]


def build_systemd(_: InteractiveSession) -> List[str]:
    return ["systemd", "install"]


def build_start_vm(session: InteractiveSession) -> List[str]:
    vms = session.load_vms()
    if not vms:
        raise click.ClickException("В конфигурации не найдено ВМ.")

    choices: list[questionary.QuestionChoice] = [questionary.Choice("Все виртуалки", value="__all__")]
    choices.extend(questionary.Choice(name, value=name) for name in vms)
    selection = _select_from_list("Какую ВМ запустить?", choices)

    args = ["start-vm", *session.config_option()]
    if selection == "__all__":
        args.append("--all-vms")
    else:
        args.append(str(selection))
    return args


def build_stop_vm(session: InteractiveSession) -> List[str]:
    vms = session.load_vms()
    if not vms:
        raise click.ClickException("В конфигурации не найдено ВМ.")

    choices: list[questionary.QuestionChoice] = [questionary.Choice("Все виртуалки", value="__all__")]
    choices.extend(questionary.Choice(name, value=name) for name in vms)
    selection = _select_from_list("Какую ВМ остановить?", choices)

    args = ["stop-vm", *session.config_option()]
    if selection == "__all__":
        args.append("--all-vms")
    else:
        args.append(str(selection))
    return args


def _command_builders() -> Dict[str, CommandBuilder]:
    return {
        "backup-once": build_backup_once,
        "backup-repeated": build_backup_repeated,
        "backup-repeated-all": build_backup_repeated_all,
        "backup-repeated-mount": build_backup_repeated_mount,
        "config-gen": build_config_gen,
        "create-vm": build_create_vm,
        "create-vms": build_create_vms,
        "mount": build_mount,
        "prepare": build_prepare,
        "shell": build_shell,
        "ssh": build_ssh,
        "portforward": build_portforward,
        "systemd": build_systemd,
        "start-vm": build_start_vm,
        "stop-vm": build_stop_vm,
        "run": build_run,
        "install-agents": build_install_agents,
        "umount": build_umount,
    }


def _ordered_commands(cli: click.Group) -> List[click.Command]:
    desired_order = [
        "backup-once",
        "backup-repeated",
        "backup-repeated-all",
        "backup-repeated-mount",
        "config-gen",
        "create-vm",
        "create-vms",
        "mount",
        "prepare",
        "shell",
        "ssh",
        "portforward",
        "systemd",
        "start-vm",
        "stop-vm",
        "run",
        "install-agents",
        "umount",
    ]
    commands: Dict[str, click.Command] = cli.commands
    ordered: List[click.Command] = []
    for name in desired_order:
        command = commands.get(name)
        if command:
            ordered.append(command)
    for name, command in commands.items():
        if command not in ordered:
            ordered.append(command)
    return ordered


def _select_command(cli: click.Group, preselected: Optional[str]) -> click.Command:
    commands = _ordered_commands(cli)
    choices = [
        questionary.Choice(f"{cmd.name:<22} {cmd.help or cmd.short_help or ''}", value=cmd)
        for cmd in commands
    ]
    if preselected:
        for cmd in commands:
            if cmd.name == preselected:
                return cmd
    selected: click.Command = _select_from_list("Выберите команду:", choices)
    return selected


def _confirm_and_run(cli: click.Group, args: List[str]) -> None:
    command_line = ["./agsekit", *args]
    rendered = " ".join(shlex.quote(part) for part in command_line)
    click.echo(f"Команда для запуска: {rendered}")
    if not questionary.confirm("Запустить команду?", default=True).ask():
        click.echo("Команда не запущена.")
        return

    cli.main(args=args, prog_name="agsekit")


def run_interactive(
    cli: click.Group, preselected_command: Optional[str] = None, default_config_path: Optional[Path] = None
) -> None:
    builders = _command_builders()
    session = InteractiveSession(default_config_path)
    command = _select_command(cli, preselected_command)
    builder = builders.get(command.name)
    if builder is None:
        raise click.ClickException(f"Команда {command.name} недоступна в интерактивном режиме.")

    args = builder(session)
    _confirm_and_run(cli, args)
