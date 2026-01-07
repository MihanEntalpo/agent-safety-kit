import os
import shutil
import subprocess
import time
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "agsekit"


def run_backup(source: Path, dest: Path, *extra_args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    command = ["python3", str(SCRIPT_PATH), "backup-once", "--source-dir", str(source), "--dest-dir", str(dest)]
    command.extend(extra_args)
    return subprocess.run(command, check=True, capture_output=capture_output, text=True)


def list_snapshots(dest: Path) -> list[Path]:
    return sorted([p for p in dest.iterdir() if p.is_dir() and "-partial" not in p.name and "-inprogress" not in p.name])


def test_backup_creates_snapshot_with_filters(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    # Prepare content and .backupignore
    (source / "kept.txt").write_text("keep me", encoding="utf-8")
    (source / "ignored.txt").write_text("ignore me", encoding="utf-8")
    (source / "static.txt").write_text("static", encoding="utf-8")
    (source / ".backupignore").write_text("ignored.txt\n", encoding="utf-8")

    leftover = dest / "leftover-partial"
    leftover.mkdir()
    (leftover / "old.tmp").write_text("should be removed", encoding="utf-8")

    run_backup(source, dest, "--exclude", "*.tmp")

    snapshots = list_snapshots(dest)
    assert len(snapshots) == 1
    snapshot = snapshots[0]

    assert (snapshot / "kept.txt").read_text(encoding="utf-8") == "keep me"
    assert not (snapshot / "ignored.txt").exists()
    assert not (snapshot / "old.tmp").exists()

    # Second run to exercise incremental copy with hard links
    time.sleep(1.1)
    (source / "kept.txt").write_text("keep me updated", encoding="utf-8")
    (source / "new.txt").write_text("new file", encoding="utf-8")

    run_backup(source, dest)

    snapshots = list_snapshots(dest)
    assert len(snapshots) == 2
    first, second = snapshots

    # Ensure unchanged file is hard-linked
    first_static = (first / "static.txt").stat()
    second_static = (second / "static.txt").stat()
    assert first_static.st_ino == second_static.st_ino

    # Changed file differs between snapshots
    assert (first / "kept.txt").read_text(encoding="utf-8") == "keep me"
    assert (second / "kept.txt").read_text(encoding="utf-8") == "keep me updated"
    assert (second / "new.txt").read_text(encoding="utf-8") == "new file"

    # No in-progress directories should remain
    assert not any("-partial" in p.name or "-inprogress" in p.name for p in dest.iterdir())


def test_backupignore_patterns_cover_common_cases(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    # Root-level ignore rules with comments, directory exclusions, wildcard filters and reinclusion.
    (source / ".backupignore").write_text(
        "\n".join(
            [
                "# Exclude logs but keep one file",
                "!logs/keep.log",
                "logs/",
                "*.tmp",
                "root-exclude.txt",
            ]
        ),
        encoding="utf-8",
    )

    logs = source / "logs"
    logs.mkdir()
    (logs / "keep.log").write_text("keep me", encoding="utf-8")
    (logs / "other.log").write_text("drop me", encoding="utf-8")

    (source / "root.tmp").write_text("tmp", encoding="utf-8")
    (source / "root-exclude.txt").write_text("exclude", encoding="utf-8")
    (source / "keep_root.txt").write_text("keep", encoding="utf-8")

    # Nested .backupignore with anchored and relative patterns plus directory exclusion.
    nested = source / "nested"
    nested.mkdir()
    (nested / ".backupignore").write_text(
        "\n".join(
            [
                "# Anchor pattern to the root",
                "!subdir/include.me",
                "subdir/",
                "/nested-secret.txt",
                "relative.txt",
            ]
        ),
        encoding="utf-8",
    )

    (nested / "nested-secret.txt").write_text("secret", encoding="utf-8")
    (nested / "relative.txt").write_text("rel", encoding="utf-8")
    (nested / "public.txt").write_text("public", encoding="utf-8")

    subdir = nested / "subdir"
    subdir.mkdir()
    (subdir / "include.me").write_text("included", encoding="utf-8")
    (subdir / "skip.me").write_text("skipped", encoding="utf-8")

    run_backup(source, dest)

    snapshots = list_snapshots(dest)
    assert len(snapshots) == 1
    snap = snapshots[0]

    # Root-level expectations
    assert (snap / "keep_root.txt").read_text(encoding="utf-8") == "keep"
    assert not (snap / "root.tmp").exists()
    assert not (snap / "root-exclude.txt").exists()

    # logs/ is excluded except for the explicitly kept file
    assert (snap / "logs" / "keep.log").read_text(encoding="utf-8") == "keep me"
    assert not (snap / "logs" / "other.log").exists()

    # Nested patterns respect anchored, relative, and directory rules
    assert not (snap / "nested" / "nested-secret.txt").exists()
    assert not (snap / "nested" / "relative.txt").exists()
    assert (snap / "nested" / "public.txt").read_text(encoding="utf-8") == "public"
    assert (snap / "nested" / "subdir" / "include.me").read_text(encoding="utf-8") == "included"
    assert not (snap / "nested" / "subdir" / "skip.me").exists()


def test_backupignore_respects_multiple_nested_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    (source / ".backupignore").write_text("\n".join(["*.tmp", "root-block.txt"]), encoding="utf-8")
    (source / "keep_root.txt").write_text("root", encoding="utf-8")
    (source / "root-block.txt").write_text("block", encoding="utf-8")
    (source / "root.tmp").write_text("tmp", encoding="utf-8")

    level1 = source / "level1"
    level1.mkdir()
    (level1 / ".backupignore").write_text(
        "\n".join(["skip1.txt", "level2a/exclude_me.txt", "!level2a/include_me.txt"]),
        encoding="utf-8",
    )
    (level1 / "keep1.txt").write_text("keep1", encoding="utf-8")
    (level1 / "skip1.txt").write_text("skip1", encoding="utf-8")
    (level1 / "level1.tmp").write_text("tmp", encoding="utf-8")

    level2a = level1 / "level2a"
    level2a.mkdir()
    (level2a / ".backupignore").write_text("\n".join(["*.log", "deep.txt"]), encoding="utf-8")
    (level2a / "keep2.txt").write_text("keep2", encoding="utf-8")
    (level2a / "exclude_me.txt").write_text("excluded", encoding="utf-8")
    (level2a / "include_me.txt").write_text("included", encoding="utf-8")
    (level2a / "trace.log").write_text("log", encoding="utf-8")
    (level2a / "deep.txt").write_text("deep", encoding="utf-8")

    deeper = level2a / "deeper"
    deeper.mkdir()
    (deeper / ".backupignore").write_text("\n".join(["blocked.txt", "!allow.txt"]), encoding="utf-8")
    (deeper / "blocked.txt").write_text("blocked", encoding="utf-8")
    (deeper / "allow.txt").write_text("allowed", encoding="utf-8")
    (deeper / "keep.txt").write_text("keep", encoding="utf-8")

    level2b = level1 / "level2b"
    level2b.mkdir()
    (level2b / ".backupignore").write_text("*.cache", encoding="utf-8")
    (level2b / "keep_b.txt").write_text("keep_b", encoding="utf-8")
    (level2b / "drop.cache").write_text("cache", encoding="utf-8")

    run_backup(source, dest)

    snapshots = list_snapshots(dest)
    assert len(snapshots) == 1
    snap = snapshots[0]

    # Root-level rules
    assert (snap / "keep_root.txt").read_text(encoding="utf-8") == "root"
    assert not (snap / "root-block.txt").exists()
    assert not (snap / "root.tmp").exists()

    # Level1 rules
    assert (snap / "level1" / "keep1.txt").read_text(encoding="utf-8") == "keep1"
    assert not (snap / "level1" / "skip1.txt").exists()
    assert not (snap / "level1" / "level1.tmp").exists()

    # Level2a rules
    assert (snap / "level1" / "level2a" / "keep2.txt").read_text(encoding="utf-8") == "keep2"
    assert (snap / "level1" / "level2a" / "include_me.txt").read_text(encoding="utf-8") == "included"
    assert not (snap / "level1" / "level2a" / "exclude_me.txt").exists()
    assert not (snap / "level1" / "level2a" / "trace.log").exists()
    assert not (snap / "level1" / "level2a" / "deep.txt").exists()

    # Deeper nested rules
    assert (snap / "level1" / "level2a" / "deeper" / "allow.txt").read_text(encoding="utf-8") == "allowed"
    assert (snap / "level1" / "level2a" / "deeper" / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not (snap / "level1" / "level2a" / "deeper" / "blocked.txt").exists()

    # Parallel nested rules
    assert (snap / "level1" / "level2b" / "keep_b.txt").read_text(encoding="utf-8") == "keep_b"
    assert not (snap / "level1" / "level2b" / "drop.cache").exists()


def test_partial_directory_removed_after_restart(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    (source / "file.txt").write_text("content", encoding="utf-8")

    command = [
        "python3",
        str(Path(__file__).resolve().parent.parent / "agsekit"),
        "backup-once",
        "--source-dir",
        str(source),
        "--dest-dir",
        str(dest),
    ]

    process = subprocess.Popen(command)

    partial_dir: Path | None = None
    deadline = time.time() + 5
    while time.time() < deadline:
        partial_candidates = [p for p in dest.iterdir() if p.is_dir() and p.name.endswith("-partial")]
        if partial_candidates:
            partial_dir = partial_candidates[0]
            break
        time.sleep(0.05)

    assert partial_dir is not None, "Partial directory was not created before interruption"

    process.terminate()
    process.wait(timeout=5)

    assert partial_dir.exists(), "Partial directory should remain after interruption"

    run_backup(source, dest)

    assert not any(p.name.endswith("-partial") for p in dest.iterdir())
    snapshots = list_snapshots(dest)
    assert len(snapshots) == 1
    assert (snapshots[0] / "file.txt").read_text(encoding="utf-8") == "content"


def test_incremental_hardlinks_preserve_unchanged_inode(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    changing = source / "changing.txt"
    stable = source / "stable.txt"

    changing.write_text("v1", encoding="utf-8")
    stable.write_text("constant", encoding="utf-8")

    run_backup(source, dest)

    time.sleep(1.1)
    changing.write_text("v2", encoding="utf-8")
    run_backup(source, dest)

    time.sleep(1.1)
    changing.write_text("v3", encoding="utf-8")
    run_backup(source, dest)

    snapshots = list_snapshots(dest)
    assert len(snapshots) == 3

    contents = [(snap / "changing.txt").read_text(encoding="utf-8") for snap in snapshots]
    assert contents == ["v1", "v2", "v3"]

    stable_inodes = [(snap / "stable.txt").stat().st_ino for snap in snapshots]
    assert len(set(stable_inodes)) == 1, "Unchanged file should be hard-linked across snapshots"

    changing_inodes = [(snap / "changing.txt").stat().st_ino for snap in snapshots]
    assert len(set(changing_inodes)) > 1, "Changed file should not reuse the same inode across all snapshots"


def test_skips_backup_when_no_changes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    (source / "file.txt").write_text("content", encoding="utf-8")

    run_backup(source, dest)

    time.sleep(1.1)
    result = run_backup(source, dest, capture_output=True)

    snapshots = list_snapshots(dest)
    assert len(snapshots) == 1
    assert "No changes detected" in (result.stdout or "")
    assert not any(p.name.endswith("-partial") for p in dest.iterdir())


def test_inode_manifest_contains_sorted_entries(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    (source / "project").mkdir()
    (source / "project" / "readme.md").write_text("info", encoding="utf-8")
    (source / "project" / "nested").mkdir()
    (source / "project" / "nested" / "file.txt").write_text("data", encoding="utf-8")

    run_backup(source, dest)

    snapshots = list_snapshots(dest)
    assert len(snapshots) == 1
    snapshot = snapshots[0]

    inode_file = snapshot / ".inodes"
    assert inode_file.exists()

    recorded_lines = inode_file.read_text(encoding="utf-8").splitlines()

    expected_entries: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(snapshot):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            rel_path = file_path.relative_to(snapshot).as_posix()
            inode = file_path.lstat().st_ino
            expected_entries.append(f"{rel_path} {inode}")

    assert recorded_lines == sorted(expected_entries)


def test_logs_cleanup_and_creation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    (source / "file.txt").write_text("data", encoding="utf-8")

    leftover_partial = dest / "old-partial"
    leftover_partial.mkdir()
    (leftover_partial / "stale.tmp").write_text("stale", encoding="utf-8")

    result = run_backup(source, dest, capture_output=True)

    assert "Removed unfinished snapshot:" in (result.stdout or "")
    assert "Running rsync to create snapshot:" in (result.stdout or "")
    assert "Snapshot created:" in (result.stdout or "")

    snapshots = list_snapshots(dest)
    assert len(snapshots) == 1
    assert (snapshots[0] / "file.txt").read_text(encoding="utf-8") == "data"
    assert not leftover_partial.exists()


def test_errors_reported_to_stderr_and_nonzero_exit(tmp_path: Path) -> None:
    dest = tmp_path / "dest"
    dest.mkdir()

    missing_source = tmp_path / "missing"

    command = [
        "python3",
        str(SCRIPT_PATH),
        "backup-once",
        "--source-dir",
        str(missing_source),
        "--dest-dir",
        str(dest),
    ]

    result = subprocess.run(command, check=False, capture_output=True, text=True)

    assert result.returncode != 0
    assert "Source directory does not exist" in (result.stderr or "")

