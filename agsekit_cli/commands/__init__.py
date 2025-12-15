"""CLI commands for agsekit."""

from __future__ import annotations

import click

non_interactive_option = click.option(
    "--non-interactive",
    is_flag=True,
    help="Отключить автоматический переход в интерактивный режим.",
)

__all__ = ["non_interactive_option"]
