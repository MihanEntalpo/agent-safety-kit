#!/usr/bin/env python3
"""Fail when the configured package version already exists on PyPI."""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python < 3.11 without stdlib tomllib
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PYPI_BASE_URLS = {
    "pypi": "https://pypi.org",
    "testpypi": "https://test.pypi.org",
}


class PyPIVersionError(Exception):
    pass


def read_project_name_version(pyproject_path: Path) -> Tuple[str, str]:
    if tomllib is None:
        raise PyPIVersionError(
            "Could not import tomllib or tomli. Use Python 3.11+ or install tomli for Python 3.9/3.10."
        )

    try:
        with pyproject_path.open("rb") as handle:
            data: Dict[str, Any] = tomllib.load(handle)
    except OSError as exc:
        raise PyPIVersionError(f"Could not read {pyproject_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:  # type: ignore[union-attr]
        raise PyPIVersionError(f"Could not parse {pyproject_path}: {exc}") from exc

    project = data.get("project")
    if not isinstance(project, dict):
        raise PyPIVersionError(f"{pyproject_path} does not contain a [project] table.")

    name = project.get("name")
    version = project.get("version")

    if not isinstance(name, str) or not name.strip():
        raise PyPIVersionError(f"{pyproject_path} project.name must be a non-empty string.")
    if not isinstance(version, str) or not version.strip():
        raise PyPIVersionError(f"{pyproject_path} project.version must be a non-empty string.")

    return name.strip(), version.strip()


def build_version_url(base_url: str, package: str, version: str) -> str:
    encoded_package = urllib.parse.quote(package, safe="")
    encoded_version = urllib.parse.quote(version, safe="")
    return f"{base_url.rstrip('/')}/pypi/{encoded_package}/{encoded_version}/json"


def pypi_version_exists(
    package: str,
    version: str,
    base_url: str,
    *,
    timeout: float = 15.0,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> bool:
    url = build_version_url(base_url, package, version)
    request = urllib.request.Request(url, headers={"User-Agent": "agsekit-release-check"})

    try:
        response = opener(request, timeout=timeout)
        with response:  # type: ignore[attr-defined]
            return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise PyPIVersionError(f"PyPI returned HTTP {exc.code} for {url}.") from exc
    except urllib.error.URLError as exc:
        raise PyPIVersionError(f"Could not query PyPI at {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise PyPIVersionError(f"Timed out while querying PyPI at {url}.") from exc


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether a package version already exists on PyPI.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Project root directory. Defaults to the repository root inferred from this script path.",
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=None,
        help="Path to pyproject.toml. Defaults to <project-root>/pyproject.toml.",
    )
    parser.add_argument("--package", default=None, help="Package name. Defaults to project.name.")
    parser.add_argument("--version", default=None, help="Package version. Defaults to project.version.")
    parser.add_argument(
        "--repository",
        choices=sorted(PYPI_BASE_URLS),
        default="pypi",
        help="Repository to check.",
    )
    parser.add_argument("--base-url", default=None, help="Override the repository base URL.")
    parser.add_argument("--timeout", type=float, default=15.0, help="Network timeout in seconds.")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    pyproject_path = (args.pyproject or project_root / "pyproject.toml").resolve()
    base_url = args.base_url or PYPI_BASE_URLS[args.repository]

    try:
        pyproject_name, pyproject_version = read_project_name_version(pyproject_path)
        package = args.package or pyproject_name
        version = args.version or pyproject_version

        if pypi_version_exists(package, version, base_url, timeout=args.timeout):
            print(
                f"Error: {args.repository} already contains {package} {version}. "
                "Bump project.version before publishing.",
                file=sys.stderr,
            )
            return 1

        print(f"{args.repository} does not contain {package} {version}.")
        return 0
    except PyPIVersionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
