#!/usr/bin/env python3
"""Extract release notes for the current pyproject.toml version."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python < 3.11 without stdlib tomllib
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SECTION_RE = re.compile(r"^##\s+([^\s]+)\s+-\s+(.+?)\s*$")


class ChangelogError(Exception):
    pass


def read_project_version(pyproject_path: Path) -> str:
    if tomllib is None:
        raise ChangelogError(
            "Could not import tomllib or tomli. Use Python 3.11+ or install tomli for Python 3.9/3.10."
        )

    try:
        with pyproject_path.open("rb") as handle:
            data: Dict[str, Any] = tomllib.load(handle)
    except OSError as exc:
        raise ChangelogError(f"Could not read {pyproject_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:  # type: ignore[union-attr]
        raise ChangelogError(f"Could not parse {pyproject_path}: {exc}") from exc

    try:
        version = data["project"]["version"]
    except KeyError as exc:
        raise ChangelogError(f"{pyproject_path} does not contain project.version.") from exc

    if not isinstance(version, str) or not version.strip():
        raise ChangelogError(f"{pyproject_path} project.version must be a non-empty string.")

    return version.strip()


def default_changelog_path(project_root: Path) -> Path:
    uppercase = project_root / "CHANGELOG.md"
    lowercase = project_root / "changelog.md"

    if uppercase.exists():
        return uppercase
    return lowercase


def find_section(lines: List[str], version: str) -> Tuple[str, str]:
    matches: List[Tuple[int, str]] = []

    for index, line in enumerate(lines):
        match = SECTION_RE.match(line)
        if match and match.group(1) == version:
            matches.append((index, match.group(2)))

    if not matches:
        raise ChangelogError(f"Changelog does not contain a section for version {version}.")

    if len(matches) > 1:
        raise ChangelogError(f"Changelog contains multiple sections for version {version}.")

    start_index, title = matches[0]
    body_start = start_index + 1
    body_end = len(lines)

    for index in range(body_start, len(lines)):
        if lines[index].startswith("## "):
            body_end = index
            break

    body = "\n".join(lines[body_start:body_end]).strip()
    if not body:
        raise ChangelogError(f"Changelog section for version {version} is empty.")

    return title, body + "\n"


def extract_notes(changelog_path: Path, version: str) -> str:
    try:
        text = changelog_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ChangelogError(f"Could not read {changelog_path}: {exc}") from exc

    lines = text.splitlines()
    _title, body = find_section(lines, version)
    return body


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract release notes from changelog.md.")
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
    parser.add_argument(
        "--changelog",
        type=Path,
        default=None,
        help="Path to the changelog. Defaults to CHANGELOG.md if present, otherwise changelog.md.",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Version to extract. Defaults to project.version from pyproject.toml.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write release notes to this file instead of stdout.",
    )
    parser.add_argument(
        "--version-only",
        action="store_true",
        help="Print the resolved pyproject.toml version and do not read the changelog.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    pyproject_path = (args.pyproject or project_root / "pyproject.toml").resolve()
    changelog_path = (args.changelog or default_changelog_path(project_root)).resolve()

    try:
        version = args.version or read_project_version(pyproject_path)
        if args.version_only:
            print(version)
            return 0

        notes = extract_notes(changelog_path, version)
        if args.output:
            args.output.write_text(notes, encoding="utf-8")
        else:
            sys.stdout.write(notes)
        return 0
    except ChangelogError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
