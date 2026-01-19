from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Sequence

import click

from .commands.backup_once import backup_once_command
from .commands.backup_clean import backup_clean_command
from .commands.backup_repeated import backup_repeated_all_command, backup_repeated_command, backup_repeated_mount_command
from .commands import non_interactive_option
from .commands.config_gen import config_gen_command
from .commands.config_example import config_example_command
from .commands.create_vm import create_vm_command, create_vms_command
from .commands.addmount import addmount_command
from .commands.removemount import removemount_command
from .commands.mounts import mount_command, umount_command
from .commands.prepare import prepare_command
from .commands.run import run_command
from .commands.shell import shell_command
from .commands.systemd import systemd_group
from .commands.ssh import ssh_command
from .commands.install_agents import install_agents_command
from .commands.list_bundles import list_bundles_command
from .commands.portforward import portforward_command
from .commands.pip_upgrade import pip_upgrade_command
from .commands.start_vm import start_vm_command
from .commands.stop import stop_vm_command
from .commands.destroy_vm import destroy_vm_command
from .config import resolve_config_path
from .i18n import set_language, tr
from .interactive import is_interactive_terminal, run_interactive

COMMANDS_REQUIRING_CONFIG = {
    "backup-repeated-all",
    "backup-repeated-mount",
    "backup-clean",
    "create-vm",
    "create-vms",
    "addmount",
    "removemount",
    "install-agents",
    "mount",
    "destroy-vm",
    "run",
    "shell",
    "ssh",
    "portforward",
    "start-vm",
    "stop-vm",
    "umount",
}


def _has_non_interactive_flag(args: Sequence[str]) -> bool:
    return "--non-interactive" in args


def _extract_command(args: Sequence[str]) -> Optional[str]:
    for arg in args:
        if not arg.startswith("-"):
            return arg
    return None


def _extract_config_argument(args: Sequence[str]) -> Optional[Path]:
    for index, arg in enumerate(args):
        if arg == "--config" and index + 1 < len(args):
            return Path(args[index + 1])
        if arg.startswith("--config="):
            return Path(arg.split("=", 1)[1])
    return None


@click.group(help=tr("cli.description"))
@non_interactive_option
def cli(non_interactive: bool) -> None:
    """Agent Safety Kit CLI."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive


def main() -> None:
    set_language()
    for command in (
        prepare_command,
        create_vm_command,
        create_vms_command,
        backup_once_command,
        backup_clean_command,
        backup_repeated_command,
        backup_repeated_mount_command,
        backup_repeated_all_command,
        addmount_command,
        removemount_command,
        mount_command,
        umount_command,
        install_agents_command,
        list_bundles_command,
        start_vm_command,
        stop_vm_command,
        run_command,
        shell_command,
        ssh_command,
        portforward_command,
        config_gen_command,
        config_example_command,
        pip_upgrade_command,
        systemd_group,
        destroy_vm_command,
    ):
        cli.add_command(command)

    args = sys.argv[1:]
    non_interactive = _has_non_interactive_flag(args)
    filtered_args = [arg for arg in args if arg != "--non-interactive"]
    command = _extract_command(filtered_args)
    explicit_config_path = _extract_config_argument(filtered_args)
    resolved_config_path = resolve_config_path(explicit_config_path)

    if is_interactive_terminal() and not non_interactive:
        if not args:
            try:
                run_interactive(cli)
            except click.ClickException as exc:
                exc.show()
                raise SystemExit(exc.exit_code)
            except click.Abort:
                raise SystemExit(1)
            return

        if command in COMMANDS_REQUIRING_CONFIG and not resolved_config_path.exists():
            click.echo(
                tr("cli.config_missing_interactive")
            )
            try:
                run_interactive(cli, preselected_command=command, default_config_path=resolved_config_path)
            except click.ClickException as exc:
                exc.show()
                raise SystemExit(exc.exit_code)
            except click.Abort:
                raise SystemExit(1)
            return

        try:
            cli.main(args=args, prog_name="agsekit", standalone_mode=False)
            return
        except click.MissingParameter:
            click.echo(tr("cli.missing_params_interactive"))
            try:
                run_interactive(cli, preselected_command=args[0] if args else None)
            except click.ClickException as exc:
                exc.show()
                raise SystemExit(exc.exit_code)
            except click.Abort:
                raise SystemExit(1)
            return
        except click.ClickException as exc:
            exc.show()
            raise SystemExit(exc.exit_code)
        except click.Abort:
            raise SystemExit(1)

    fallback_args = args
    if non_interactive and not filtered_args:
        fallback_args = ["--help"]

    try:
        cli.main(args=fallback_args, prog_name="agsekit", standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        raise SystemExit(exc.exit_code)
    except click.Abort:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
