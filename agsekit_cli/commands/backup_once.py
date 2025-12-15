from __future__ import annotations

from pathlib import Path

import click

from ..backup import backup_once


@click.command(name="backup-once")
@click.option("--source-dir", required=True, type=click.Path(file_okay=False, path_type=Path), help="Директория для бэкапа")
@click.option("--dest-dir", required=True, type=click.Path(file_okay=False, path_type=Path), help="Куда складывать снапшоты")
@click.option(
    "--exclude",
    "excludes",
    multiple=True,
    help="Дополнительный паттерн исключений rsync; можно указать несколько раз",
)
def backup_once_command(source_dir: Path, dest_dir: Path, excludes: tuple[str, ...]) -> None:
    """Run a single backup of a directory."""

    click.echo(f"Running one-off backup from {source_dir} to {dest_dir}...")
    backup_once(source_dir, dest_dir, extra_excludes=list(excludes))
