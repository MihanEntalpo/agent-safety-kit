"""CLI commands for agsekit."""

from __future__ import annotations

import click

from ..i18n import tr

non_interactive_option = click.option(
    "--non-interactive",
    is_flag=True,
    help=tr("cli.non_interactive_help"),
)

__all__ = ["non_interactive_option"]
