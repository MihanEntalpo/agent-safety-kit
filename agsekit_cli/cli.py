from __future__ import annotations

import sys
from typing import Sequence

import click

from .commands.backup_once import backup_once_command
from .commands.backup_repeated import backup_repeated_all_command, backup_repeated_command, backup_repeated_mount_command
from .commands import non_interactive_option
from .commands.create_vm import create_vm_command, create_vms_command
from .commands.mounts import mount_command, umount_command
from .commands.prepare import prepare_command
from .commands.run import run_command
from .commands.shell import shell_command
from .commands.install_agents import install_agents_command
from .interactive import is_interactive_terminal, run_interactive


def _has_non_interactive_flag(args: Sequence[str]) -> bool:
    return "--non-interactive" in args


@click.group()
@non_interactive_option
def cli(non_interactive: bool) -> None:
    """Agent Safety Kit CLI."""


def main() -> None:
    for command in (
        prepare_command,
        create_vm_command,
        create_vms_command,
        backup_once_command,
        backup_repeated_command,
        backup_repeated_mount_command,
        backup_repeated_all_command,
        mount_command,
        umount_command,
        install_agents_command,
        run_command,
        shell_command,
    ):
        cli.add_command(command)

    args = sys.argv[1:]
    non_interactive = _has_non_interactive_flag(args)
    filtered_args = [arg for arg in args if arg != "--non-interactive"]

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

        try:
            cli.main(args=args, prog_name="agsekit", standalone_mode=False)
            return
        except click.MissingParameter:
            click.echo("Недостаточно параметров: запускается интерактивный режим...")
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
