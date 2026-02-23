"""CLI commands for agsekit."""

from __future__ import annotations

import click

from ..i18n import tr

non_interactive_option = click.option(
    "--non-interactive",
    is_flag=True,
    help=tr("cli.non_interactive_help"),
)

debug_option = click.option(
    "--debug",
    is_flag=True,
    help=tr("debug.option"),
)

__all__ = ["debug_option", "non_interactive_option"]
