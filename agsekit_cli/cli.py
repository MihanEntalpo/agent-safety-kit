from __future__ import annotations

import click

from .commands.backup_once import backup_once_command
from .commands.create_vm import create_vm_command
from .commands.prepare import prepare_command


@click.group()
def cli() -> None:
    """Agent Safety Kit CLI."""


def main() -> None:
    for command in (prepare_command, create_vm_command, backup_once_command):
        cli.add_command(command)
    cli(prog_name="agsekit")


if __name__ == "__main__":
    main()
