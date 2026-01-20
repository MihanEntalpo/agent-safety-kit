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
from .i18n import tr
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
            tr("interactive.config_path_prompt"),
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
                click.echo(tr("interactive.config_load_failed", error=exc))
                self._config_cache = None

    def _load_from_config(
        self, loader: Callable[[Dict[str, object]], Union[Dict[str, object], List[object]]], description: str
    ) -> Union[Dict[str, object], List[object]]:
        while True:
            config = self._load_config()
            try:
                return loader(config)
            except ConfigError as exc:
                click.echo(tr("interactive.config_section_error", section=description, error=exc))
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
    while questionary.confirm(tr("interactive.exclude_add_prompt"), default=False).ask():
        value = questionary.text(tr("interactive.exclude_pattern_prompt")).ask()
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
    source_dir = _select_directory(tr("interactive.backup_once_source_prompt"))
    dest_dir = _select_directory(tr("interactive.backup_once_dest_prompt"))
    excludes = _collect_excludes()

    args = ["backup-once", "--source-dir", str(source_dir), "--dest-dir", str(dest_dir)]
    for pattern in excludes:
        args.extend(["--exclude", pattern])
    return args


def build_backup_repeated(session: InteractiveSession) -> List[str]:
    source_dir = _select_directory(tr("interactive.backup_repeated_source_prompt"))
    dest_dir = _select_directory(tr("interactive.backup_repeated_dest_prompt"))
    interval_raw = questionary.text(tr("interactive.backup_repeated_interval_prompt"), default="5").ask()
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
        raise click.ClickException(tr("interactive.no_mounts"))

    choices = [
        questionary.Choice(f"{mount.source} -> {mount.vm_name}:{mount.target}", value=mount)
        for mount in mounts
    ]
    selected: MountConfig = _select_from_list(tr("interactive.mount_backup_select"), choices)
    return ["backup-repeated-mount", "--mount", str(selected.source), *session.config_option()]


def build_backup_repeated_all(session: InteractiveSession) -> List[str]:
    session.load_mounts()
    return ["backup-repeated-all", *session.config_option()]


def build_backup_clean(session: InteractiveSession) -> List[str]:
    mounts = session.load_mounts()
    if not mounts:
        raise click.ClickException(tr("interactive.no_mounts"))

    choices = [
        questionary.Choice(f"{mount.source} -> {mount.vm_name}:{mount.target}", value=mount)
        for mount in mounts
    ]
    selected: MountConfig = _select_from_list(tr("interactive.mount_backup_select"), choices)

    keep_raw = questionary.text(tr("interactive.backup_clean_keep_prompt"), default="50").ask()
    if keep_raw is None:
        raise click.Abort()
    keep_value = keep_raw.strip() or "50"

    method_choices = [
        questionary.Choice(tr("interactive.backup_clean_method_thin"), value="thin"),
        questionary.Choice(tr("interactive.backup_clean_method_tail"), value="tail"),
    ]
    method = _select_from_list(tr("interactive.backup_clean_method_prompt"), method_choices)

    return ["backup-clean", str(selected.source), keep_value, str(method), *session.config_option()]


def build_config_example(session: InteractiveSession) -> List[str]:
    return ["config-example"]


def build_pip_upgrade(_: InteractiveSession) -> List[str]:
    return ["pip-upgrade"]


def build_create_vm(session: InteractiveSession) -> List[str]:
    vms = session.load_vms()
    vm_choices = [questionary.Choice(name, value=name) for name in vms]
    vm_choices.append(questionary.Choice(tr("interactive.vm_manual_entry"), value=None))
    vm_name = _select_from_list(tr("interactive.create_vm_select"), vm_choices)
    if vm_name is None:
        manual = questionary.text(tr("interactive.vm_name_prompt")).ask()
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
        raise click.ClickException(tr("interactive.no_mounts"))

    all_choice = questionary.Choice(tr("interactive.mounts_all_choice"), value="__all__")
    choices: list[questionary.QuestionChoice] = [all_choice]
    for mount in mounts:
        label = f"{mount.source} -> {mount.vm_name}:{mount.target}"
        choices.append(questionary.Choice(label, value=mount))

    selection = _select_from_list(tr("interactive.mount_action_prompt", action=action), choices)
    if selection == "__all__":
        return [f"--all"]
    assert isinstance(selection, MountConfig)
    return ["--source-dir", str(selection.source)]


def build_mount(session: InteractiveSession) -> List[str]:
    selection = _select_mount_choice(session, tr("interactive.mount_action_mount"))
    return ["mount", *selection, *session.config_option()]


def build_addmount(_: InteractiveSession) -> List[str]:
    return ["addmount"]


def build_removemount(_: InteractiveSession) -> List[str]:
    return ["removemount"]


def build_umount(session: InteractiveSession) -> List[str]:
    selection = _select_mount_choice(session, tr("interactive.mount_action_umount"))
    return ["umount", *selection, *session.config_option()]


def build_install_agents(session: InteractiveSession) -> List[str]:
    agents = session.load_agents()
    if not agents:
        raise click.ClickException(tr("interactive.no_agents"))
    vms = session.load_vms()

    agent_choices: list[questionary.QuestionChoice] = [questionary.Choice(tr("interactive.agents_all"), value="__all__")]
    agent_choices.extend(questionary.Choice(name, value=name) for name in agents)
    agent_choice = _select_from_list(tr("interactive.agent_install_select"), agent_choices)

    default_vm = next(iter(vms.keys())) if vms else None
    default_vm_label = tr("interactive.vm_default_label")
    if default_vm:
        default_vm_label += f" ({default_vm})"

    vm_choices: list[questionary.QuestionChoice] = [questionary.Choice(default_vm_label, value="__default__")]
    vm_choices.extend(questionary.Choice(name, value=name) for name in vms)
    vm_choices.append(questionary.Choice(tr("interactive.vms_all"), value="__all_vms__"))
    vm_choice = _select_from_list(tr("interactive.agent_install_target"), vm_choices)

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
        raise click.ClickException(tr("interactive.no_agents"))
    mounts = session.load_mounts()
    vms = session.load_vms()

    agent_choices = [questionary.Choice(name, value=agent) for name, agent in agents.items()]
    agent: AgentConfig = _select_from_list(tr("interactive.agent_run_select"), agent_choices)

    mount_choices: list[questionary.QuestionChoice] = [
        questionary.Choice(tr("interactive.mount_select_none"), value=None),
    ]
    mount_choices.extend(
        questionary.Choice(f"{mount.source} -> {mount.vm_name}:{mount.target}", value=mount) for mount in mounts
    )
    mount_choices.append(questionary.Choice(tr("interactive.mount_select_custom"), value="__custom__"))
    mount_choice = _select_from_list(tr("interactive.mount_select_prompt"), mount_choices)

    source_dir: Optional[Path] = None
    if isinstance(mount_choice, MountConfig):
        source_dir = mount_choice.source
    elif mount_choice == "__custom__":
        source_dir = _select_directory(tr("interactive.mount_custom_path"))

    auto_vm_value = "__auto_vm__"
    vm_choices: list[questionary.QuestionChoice] = [
        questionary.Choice(tr("interactive.vm_select_auto"), value=auto_vm_value)
    ]
    vm_choices.extend(questionary.Choice(name, value=name) for name in vms)
    vm_choice = _select_from_list(tr("interactive.vm_select_prompt"), vm_choices)

    if vm_choice == auto_vm_value:
        vm_choice = None

    disable_backups = questionary.confirm(tr("interactive.disable_backups_prompt"), default=False).ask()
    if disable_backups is None:
        raise click.Abort()

    agent_args_raw = questionary.text(tr("interactive.agent_args_prompt"), default="").ask()
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
        raise click.ClickException(tr("interactive.no_vms"))

    choices = [questionary.Choice(name, value=name) for name in vms]
    vm_name = _select_from_list(tr("interactive.shell_select_vm"), choices)
    return ["shell", str(vm_name), *session.config_option()]


def build_ssh(session: InteractiveSession) -> List[str]:
    vms = session.load_vms()
    if not vms:
        raise click.ClickException(tr("interactive.no_vms"))

    choices = [questionary.Choice(name, value=name) for name in vms]
    vm_name = _select_from_list(tr("interactive.ssh_select_vm"), choices)

    ssh_args_raw = questionary.text(tr("interactive.ssh_args_prompt"), default="").ask()
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
        raise click.ClickException(tr("interactive.no_vms"))

    choices: list[questionary.QuestionChoice] = [questionary.Choice(tr("interactive.vms_all"), value="__all__")]
    choices.extend(questionary.Choice(name, value=name) for name in vms)
    selection = _select_from_list(tr("interactive.start_vm_select"), choices)

    args = ["start-vm", *session.config_option()]
    if selection == "__all__":
        args.append("--all-vms")
    else:
        args.append(str(selection))
    return args


def build_stop_vm(session: InteractiveSession) -> List[str]:
    vms = session.load_vms()
    if not vms:
        raise click.ClickException(tr("interactive.no_vms"))

    choices: list[questionary.QuestionChoice] = [questionary.Choice(tr("interactive.vms_all"), value="__all__")]
    choices.extend(questionary.Choice(name, value=name) for name in vms)
    selection = _select_from_list(tr("interactive.stop_vm_select"), choices)

    args = ["stop-vm", *session.config_option()]
    if selection == "__all__":
        args.append("--all-vms")
    else:
        args.append(str(selection))
    return args


def build_destroy_vm(session: InteractiveSession) -> List[str]:
    vms = session.load_vms()
    if not vms:
        raise click.ClickException(tr("interactive.no_vms"))

    choices: list[questionary.QuestionChoice] = [questionary.Choice(tr("interactive.vms_all"), value="__all__")]
    choices.extend(questionary.Choice(name, value=name) for name in vms)
    selection = _select_from_list(tr("interactive.destroy_vm_select"), choices)

    args = ["destroy-vm", *session.config_option()]
    if selection == "__all__":
        args.append("--all")
    else:
        args.append(str(selection))
    return args


def _command_builders() -> Dict[str, CommandBuilder]:
    return {
        "backup-once": build_backup_once,
        "backup-repeated": build_backup_repeated,
        "backup-repeated-all": build_backup_repeated_all,
        "backup-repeated-mount": build_backup_repeated_mount,
        "backup-clean": build_backup_clean,
        "config-example": build_config_example,
        "config-gen": build_config_gen,
        "pip-upgrade": build_pip_upgrade,
        "create-vm": build_create_vm,
        "create-vms": build_create_vms,
        "addmount": build_addmount,
        "removemount": build_removemount,
        "mount": build_mount,
        "prepare": build_prepare,
        "shell": build_shell,
        "ssh": build_ssh,
        "portforward": build_portforward,
        "systemd": build_systemd,
        "start-vm": build_start_vm,
        "stop-vm": build_stop_vm,
        "destroy-vm": build_destroy_vm,
        "run": build_run,
        "install-agents": build_install_agents,
        "umount": build_umount,
    }


def _select_command(cli: click.Group, preselected: Optional[str]) -> click.Command:
    commands: Dict[str, click.Command] = cli.commands
    if preselected:
        preselected_command = commands.get(preselected)
        if preselected_command:
            return preselected_command

    sections = [
        (
            tr("interactive.section_init_config"),
            ["prepare", "config-example", "config-gen", "pip-upgrade"],
        ),
        (
            tr("interactive.section_virtual_machines"),
            ["create-vms", "create-vm", "stop-vm", "start-vm", "destroy-vm"],
        ),
        (tr("interactive.section_mounts"), ["mount", "umount", "addmount", "removemount"]),
        (
            tr("interactive.section_agents_shell"),
            ["install-agents", "run", "shell", "ssh", "portforward"],
        ),
        (tr("interactive.section_daemon_control"), ["systemd"]),
        (
            tr("interactive.section_manual_backup"),
            ["backup-once", "backup-repeated", "backup-repeated-mount", "backup-repeated-all", "backup-clean"],
        ),
    ]

    choices: list[questionary.QuestionChoice] = []
    for title, names in sections:
        choices.append(questionary.Separator(title))
        for name in names:
            command = commands.get(name)
            if command:
                choices.append(
                    questionary.Choice(f"{command.name:<22} {command.help or command.short_help or ''}", value=command)
                )
    selected: click.Command = _select_from_list(tr("interactive.command_select"), choices)
    return selected


def _confirm_and_run(cli: click.Group, args: List[str]) -> None:
    command_line = ["agsekit", *args]
    rendered = " ".join(shlex.quote(part) for part in command_line)
    click.echo(tr("interactive.command_preview", command=rendered))
    if not questionary.confirm(tr("interactive.command_confirm"), default=True).ask():
        click.echo(tr("interactive.command_cancelled"))
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
        raise click.ClickException(tr("interactive.command_not_available", command=command.name))

    args = builder(session)
    _confirm_and_run(cli, args)
