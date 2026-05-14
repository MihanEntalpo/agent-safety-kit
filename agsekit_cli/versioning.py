from __future__ import annotations

import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Optional

from packaging.version import InvalidVersion, Version


def installed_version() -> Optional[str]:
    """Return the installed agsekit distribution version when available."""
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


def find_pyproject_version() -> Optional[str]:
    """Search upwards from the cwd and package directory for pyproject.toml and return project.version."""
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


def runtime_version() -> Optional[str]:
    """Return the version of the currently running agsekit build."""
    return installed_version() or find_pyproject_version()


def normalize_version(value: object) -> Optional[str]:
    """Return a normalized PEP 440 version string or None when the value is not a valid version."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return str(Version(cleaned))
    except InvalidVersion:
        return None


def is_newer_version(candidate: Optional[str], current: Optional[str]) -> bool:
    """Return True when candidate is a valid version newer than current."""
    normalized_candidate = normalize_version(candidate)
    normalized_current = normalize_version(current)
    if normalized_candidate is None or normalized_current is None:
        return False
    return Version(normalized_candidate) > Version(normalized_current)


def latest_version_via_pip(package_name: str = "agsekit", *, timeout: float = 60.0) -> str:
    """Ask pip for the latest published version of a package and return the highest available version."""
    command = [
        sys.executable,
        "-m",
        "pip",
        "index",
        "versions",
        package_name,
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "pip index versions failed"
        raise RuntimeError(details)

    available_line = None
    for line in result.stdout.splitlines():
        if line.startswith("Available versions:"):
            available_line = line
            break
    if available_line is None:
        raise RuntimeError("pip did not report available versions")

    versions = [part.strip() for part in available_line.split(":", 1)[1].split(",")]
    for version in versions:
        normalized = normalize_version(version)
        if normalized is not None:
            return normalized
    raise RuntimeError("pip did not report a valid version")
