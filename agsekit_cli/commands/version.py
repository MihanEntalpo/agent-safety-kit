from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path
from typing import Optional

import click

from ..i18n import tr


def _installed_version() -> Optional[str]:
    try:
        return metadata.version("agsekit")
    except metadata.PackageNotFoundError:
        return None


def _parse_pyproject_version(content: str) -> Optional[str]:
    try:
        import tomllib  # type: ignore[attr-defined]
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            tomllib = None

    if tomllib is not None:
        try:
            data = tomllib.loads(content)
            project = data.get("project", {}) if isinstance(data, dict) else {}
            version = project.get("version") if isinstance(project, dict) else None
            if isinstance(version, str) and version:
                return version
        except Exception:
            pass

    in_project = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if in_project:
            match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    return None


def _find_pyproject_version() -> Optional[str]:
    search_roots = [Path.cwd(), Path(__file__).resolve().parent]
    seen = set()
    for root in search_roots:
        for candidate in [root, *root.parents]:
            if candidate in seen:
                continue
            seen.add(candidate)
            pyproject_path = candidate / "pyproject.toml"
            if pyproject_path.exists():
                try:
                    content = pyproject_path.read_text(encoding="utf-8")
                except OSError:
                    return None
                return _parse_pyproject_version(content)
    return None


@click.command(name="version", help=tr("version.command_help"))
def version_command() -> None:
    installed = _installed_version()
    project = _find_pyproject_version()

    if not installed and not project:
        raise click.ClickException(tr("version.unavailable"))

    if installed:
        click.echo(tr("version.installed", version=installed))
    if project:
        click.echo(tr("version.project", version=project))
