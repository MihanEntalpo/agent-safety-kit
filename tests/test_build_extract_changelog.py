import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build" / "extract_changelog.py"

spec = importlib.util.spec_from_file_location("extract_changelog", SCRIPT_PATH)
assert spec is not None
extract_changelog = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(extract_changelog)


def test_extract_changelog_uses_exact_version_not_first_section(tmp_path: Path) -> None:
    changelog = tmp_path / "changelog.md"
    changelog.write_text(
        """# Versions

## 2.0.0 - Newer

* wrong section

## 1.2.3 - Target

* expected section
""",
        encoding="utf-8",
    )

    assert extract_changelog.extract_notes(changelog, "1.2.3") == "* expected section\n"


def test_extract_changelog_fails_when_version_missing(tmp_path: Path) -> None:
    changelog = tmp_path / "changelog.md"
    changelog.write_text("## 1.0.0 - Existing\n\n* item\n", encoding="utf-8")

    try:
        extract_changelog.extract_notes(changelog, "9.9.9")
    except extract_changelog.ChangelogError as exc:
        assert "does not contain a section for version 9.9.9" in str(exc)
    else:
        raise AssertionError("missing changelog version should fail")


def test_extract_changelog_fails_when_section_empty(tmp_path: Path) -> None:
    changelog = tmp_path / "changelog.md"
    changelog.write_text("## 1.2.3 - Empty\n\n## 1.2.2 - Previous\n\n* item\n", encoding="utf-8")

    try:
        extract_changelog.extract_notes(changelog, "1.2.3")
    except extract_changelog.ChangelogError as exc:
        assert "section for version 1.2.3 is empty" in str(exc)
    else:
        raise AssertionError("empty changelog section should fail")
