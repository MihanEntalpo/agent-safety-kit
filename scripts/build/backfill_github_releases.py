#!/usr/bin/env python3
"""Backfill GitHub Releases for versions already published on PyPI."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_pypi_version import PYPI_BASE_URLS, pypi_version_exists, read_project_name_version  # noqa: E402
from extract_changelog import SECTION_RE, default_changelog_path  # noqa: E402


class BackfillError(Exception):
    pass


@dataclass(frozen=True)
class ChangelogSection:
    version: str
    title: str
    body: str


@dataclass(frozen=True)
class RemoteTag:
    tag: str
    commit: str


def require_command(command: str) -> None:
    if shutil.which(command) is None:
        raise BackfillError(f"{command} is required.")


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(command),
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise BackfillError(f"Command failed: {' '.join(command)}\n{details}")
    return result


def ensure_apply_git_state(project_root: Path) -> None:
    status = run_command(["git", "status", "--porcelain"], cwd=project_root).stdout.strip()
    if status:
        raise BackfillError("Git working tree is not clean. Commit or stash changes before --apply.")

    branch = run_command(["git", "branch", "--show-current"], cwd=project_root).stdout.strip()
    if branch != "main":
        raise BackfillError(f"--apply must run from main; current branch is {branch}.")


def parse_changelog_sections(text: str) -> List[ChangelogSection]:
    lines = text.splitlines()
    headers: List[Tuple[int, str, str]] = []

    for index, line in enumerate(lines):
        match = SECTION_RE.match(line)
        if match:
            headers.append((index, match.group(1), match.group(2)))

    sections: List[ChangelogSection] = []
    for header_index, (line_index, version, title) in enumerate(headers):
        next_line_index = headers[header_index + 1][0] if header_index + 1 < len(headers) else len(lines)
        body = "\n".join(lines[line_index + 1 : next_line_index]).strip()
        if not body:
            raise BackfillError(f"Changelog section for version {version} is empty.")
        sections.append(ChangelogSection(version=version, title=title, body=body + "\n"))

    return sections


def load_changelog_sections(changelog_path: Path) -> List[ChangelogSection]:
    try:
        text = changelog_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BackfillError(f"Could not read {changelog_path}: {exc}") from exc

    sections = parse_changelog_sections(text)
    if not sections:
        raise BackfillError(f"No changelog sections found in {changelog_path}.")
    return sections


def parse_pyproject_version(text: str) -> Optional[str]:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10 only
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError as exc:
            raise BackfillError(
                "Could not import tomllib or tomli. Use Python 3.11+ or install tomli for Python 3.9/3.10."
            ) from exc

    data = tomllib.loads(text)
    project = data.get("project")
    if not isinstance(project, dict):
        return None
    version = project.get("version")
    if not isinstance(version, str) or not version.strip():
        return None
    return version.strip()


def find_first_version_commits(project_root: Path, ref: str) -> Dict[str, str]:
    commits_output = run_command(
        ["git", "rev-list", "--reverse", ref, "--", "pyproject.toml"],
        cwd=project_root,
    ).stdout
    commits = [line.strip() for line in commits_output.splitlines() if line.strip()]
    version_commits: Dict[str, str] = {}

    for commit in commits:
        show_result = run_command(
            ["git", "show", f"{commit}:pyproject.toml"],
            cwd=project_root,
            check=False,
        )
        if show_result.returncode != 0:
            continue
        version = parse_pyproject_version(show_result.stdout)
        if version and version not in version_commits:
            version_commits[version] = commit

    return version_commits


def parse_remote_tag(lines: str, tag: str) -> Optional[RemoteTag]:
    direct_ref = f"refs/tags/{tag}"
    peeled_ref = f"refs/tags/{tag}^{{}}"
    direct_sha: Optional[str] = None
    peeled_sha: Optional[str] = None

    for line in lines.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        sha, ref = parts
        if ref == direct_ref:
            direct_sha = sha
        elif ref == peeled_ref:
            peeled_sha = sha

    if peeled_sha:
        return RemoteTag(tag=tag, commit=peeled_sha)
    if direct_sha:
        return RemoteTag(tag=tag, commit=direct_sha)
    return None


def get_remote_tag(project_root: Path, tag: str) -> Optional[RemoteTag]:
    result = run_command(
        ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
        cwd=project_root,
    )
    return parse_remote_tag(result.stdout, tag)


def get_local_tag_commit(project_root: Path, tag: str) -> Optional[str]:
    result = run_command(
        ["git", "rev-parse", "--quiet", "--verify", f"{tag}^{{commit}}"],
        cwd=project_root,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def ensure_remote_tag(project_root: Path, tag: str, commit: str, *, apply: bool) -> None:
    remote_tag = get_remote_tag(project_root, tag)
    if remote_tag:
        if remote_tag.commit != commit:
            raise BackfillError(f"Remote tag {tag} points to {remote_tag.commit}, expected {commit}.")
        print(f"  tag: {tag} already exists on origin and points to the expected commit")
        return

    if not apply:
        print(f"  tag: would create and push {tag} at {commit}")
        return

    local_commit = get_local_tag_commit(project_root, tag)
    if local_commit:
        if local_commit != commit:
            raise BackfillError(f"Local tag {tag} points to {local_commit}, expected {commit}.")
        print(f"  tag: reusing local {tag} at {commit}")
    else:
        print(f"  tag: creating local annotated {tag} at {commit}")
        run_command(["git", "tag", "-a", tag, commit, "-m", f"Release {tag}"], cwd=project_root)

    print(f"  tag: pushing {tag} to origin")
    run_command(["git", "push", "origin", tag], cwd=project_root)


def github_release_exists(project_root: Path, tag: str) -> bool:
    result = run_command(
        ["gh", "release", "view", tag, "--json", "tagName", "--jq", ".tagName"],
        cwd=project_root,
        check=False,
    )
    if result.returncode == 0:
        return True

    details = f"{result.stdout}\n{result.stderr}".lower()
    if "not found" in details or "404" in details or "could not resolve" in details:
        return False

    raise BackfillError(f"Could not check GitHub Release {tag}:\n{result.stderr or result.stdout}")


def create_github_release(project_root: Path, tag: str, body: str, *, apply: bool) -> None:
    if github_release_exists(project_root, tag):
        print(f"  release: {tag} already exists")
        return

    if not apply:
        print(f"  release: would create GitHub Release {tag}")
        return

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as notes_file:
        notes_file.write(body)
        notes_path = Path(notes_file.name)

    try:
        print(f"  release: creating GitHub Release {tag}")
        run_command(
            [
                "gh",
                "release",
                "create",
                tag,
                "--verify-tag",
                "--title",
                tag,
                "--notes-file",
                str(notes_path),
            ],
            cwd=project_root,
        )
    finally:
        notes_path.unlink(missing_ok=True)


def selected_sections(sections: Iterable[ChangelogSection], requested_versions: Sequence[str]) -> List[ChangelogSection]:
    if not requested_versions:
        return list(sections)

    by_version = {section.version: section for section in sections}
    missing = [version for version in requested_versions if version not in by_version]
    if missing:
        raise BackfillError(f"Requested version(s) are missing from changelog: {', '.join(missing)}")
    return [by_version[version] for version in requested_versions]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill GitHub Releases for PyPI-published changelog versions.")
    parser.add_argument("--apply", action="store_true", help="Actually create/push missing tags and GitHub Releases.")
    parser.add_argument(
        "--version",
        action="append",
        default=[],
        help="Only process this version. Can be provided multiple times.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Project root directory. Defaults to the repository root inferred from this script path.",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=None,
        help="Path to changelog. Defaults to CHANGELOG.md if present, otherwise changelog.md.",
    )
    parser.add_argument("--ref", default="HEAD", help="Git ref whose history should be inspected. Defaults to HEAD.")
    parser.add_argument(
        "--repository",
        choices=sorted(PYPI_BASE_URLS),
        default="pypi",
        help="PyPI repository to check.",
    )
    parser.add_argument("--base-url", default=None, help="Override PyPI repository base URL.")
    parser.add_argument("--timeout", type=float, default=15.0, help="PyPI network timeout in seconds.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    changelog_path = (args.changelog or default_changelog_path(project_root)).resolve()
    base_url = args.base_url or PYPI_BASE_URLS[args.repository]

    try:
        require_command("git")
        require_command("gh")
        if args.apply:
            ensure_apply_git_state(project_root)

        package_name, _current_version = read_project_name_version(project_root / "pyproject.toml")
        all_sections = load_changelog_sections(changelog_path)
        sections = selected_sections(all_sections, args.version)
        version_commits = find_first_version_commits(project_root, args.ref)

        print("Mode: apply" if args.apply else "Mode: dry-run")
        print(f"Package: {package_name}")
        print(f"Changelog: {changelog_path}")
        print(f"Git history ref: {args.ref}")

        errors = 0
        processed = 0
        skipped_not_pypi = 0
        already_done = 0

        for section in sections:
            tag = f"v{section.version}"
            print("")
            print(f"Version {section.version}: {section.title}")

            if not pypi_version_exists(package_name, section.version, base_url, timeout=args.timeout):
                print(f"  pypi: {package_name} {section.version} is not published; skipping")
                skipped_not_pypi += 1
                continue

            print(f"  pypi: {package_name} {section.version} exists")
            commit = version_commits.get(section.version)
            if not commit:
                print(f"  error: could not find a commit where pyproject.toml first had version {section.version}")
                errors += 1
                continue
            print(f"  commit: {commit}")

            try:
                remote_before = get_remote_tag(project_root, tag)
                release_before = github_release_exists(project_root, tag) if remote_before else False
                ensure_remote_tag(project_root, tag, commit, apply=args.apply)
                create_github_release(project_root, tag, section.body, apply=args.apply)
                if remote_before and release_before:
                    already_done += 1
                else:
                    processed += 1
            except BackfillError as exc:
                print(f"  error: {exc}")
                errors += 1

        print("")
        print(
            "Summary: "
            f"processed={processed}, already_done={already_done}, "
            f"skipped_not_pypi={skipped_not_pypi}, errors={errors}"
        )
        return 1 if errors else 0
    except BackfillError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
