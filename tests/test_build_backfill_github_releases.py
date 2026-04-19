import importlib.util
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build" / "backfill_github_releases.py"

spec = importlib.util.spec_from_file_location("backfill_github_releases", SCRIPT_PATH)
assert spec is not None
backfill = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["backfill_github_releases"] = backfill
spec.loader.exec_module(backfill)


def run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_parse_changelog_sections() -> None:
    sections = backfill.parse_changelog_sections(
        """# History

## 1.2.0 - New feature

* added feature

## 1.1.0 - Fix

* fixed bug
"""
    )

    assert [section.version for section in sections] == ["1.2.0", "1.1.0"]
    assert sections[0].title == "New feature"
    assert sections[0].body == "* added feature\n"


def test_parse_remote_tag_prefers_peeled_commit_for_annotated_tags() -> None:
    output = """aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\trefs/tags/v1.2.3
bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\trefs/tags/v1.2.3^{}
"""

    tag = backfill.parse_remote_tag(output, "v1.2.3")

    assert tag == backfill.RemoteTag(tag="v1.2.3", commit="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")


def test_parse_remote_tag_uses_direct_commit_for_lightweight_tags() -> None:
    output = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\trefs/tags/v1.2.3\n"

    tag = backfill.parse_remote_tag(output, "v1.2.3")

    assert tag == backfill.RemoteTag(tag="v1.2.3", commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")


def test_selected_sections_fails_on_unknown_requested_version() -> None:
    sections = [backfill.ChangelogSection("1.0.0", "Title", "* body\n")]

    try:
        backfill.selected_sections(sections, ["9.9.9"])
    except backfill.BackfillError as exc:
        assert "Requested version(s) are missing from changelog: 9.9.9" in str(exc)
    else:
        raise AssertionError("unknown requested versions should fail")


def test_find_first_version_commits_uses_first_commit_where_version_appeared(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "main")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test")

    pyproject = repo / "pyproject.toml"
    pyproject.write_text('[project]\nname = "agsekit"\nversion = "1.0.0"\n', encoding="utf-8")
    run_git(repo, "add", "pyproject.toml")
    run_git(repo, "commit", "-m", "version 1.0.0")
    first_v1_commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    pyproject.write_text('[project]\nname = "agsekit"\nversion = "1.1.0"\n', encoding="utf-8")
    run_git(repo, "add", "pyproject.toml")
    run_git(repo, "commit", "-m", "version 1.1.0")
    first_v11_commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    pyproject.write_text('[project]\nname = "agsekit"\nversion = "1.1.0"\ndescription = "same version"\n', encoding="utf-8")
    run_git(repo, "add", "pyproject.toml")
    run_git(repo, "commit", "-m", "same version metadata")

    version_commits = backfill.find_first_version_commits(repo, "HEAD")

    assert version_commits["1.0.0"] == first_v1_commit
    assert version_commits["1.1.0"] == first_v11_commit
