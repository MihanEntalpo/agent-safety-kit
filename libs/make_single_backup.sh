#!/usr/bin/env python3
"""Single-run backup helper built around rsync.

This script performs an incremental backup from a source directory to a
destination directory, optionally using hard links to the previous backup and
applying exclusion rules from `.backupignore` files and command-line flags.
"""

import argparse
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import sys
from typing import Iterable, List, Tuple

FilterRule = Tuple[str, str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a single backup snapshot with optional hard links.")
    parser.add_argument("--source-dir", required=True, help="Directory to back up")
    parser.add_argument("--dest-dir", required=True, help="Destination directory for backups")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional rsync-style exclude pattern; can be provided multiple times",
    )
    return parser.parse_args()


def gather_backupignore_rules(source_dir: Path) -> List[FilterRule]:
    rules: List[FilterRule] = []
    for dirpath, _dirnames, filenames in os.walk(source_dir):
        if ".backupignore" not in filenames:
            continue

        ignore_path = Path(dirpath) / ".backupignore"
        rel_prefix = Path(dirpath).relative_to(source_dir)
        with ignore_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                action = "+" if line.startswith("!") else "-"
                pattern_body = line[1:] if action == "+" else line
                normalized = normalize_pattern(pattern_body, rel_prefix)
                if not normalized:
                    continue
                rules.append((action, normalized))
    return rules


def normalize_pattern(pattern: str, rel_prefix: Path) -> str:
    pattern = pattern.lstrip()
    if pattern.startswith("/"):
        pattern = pattern[1:]

    prefix_str = "" if str(rel_prefix) == "." else rel_prefix.as_posix()
    full_pattern = pattern
    if prefix_str:
        full_pattern = f"{prefix_str}/{pattern}" if pattern else prefix_str

    if full_pattern.endswith("/"):
        full_pattern = f"{full_pattern}**"

    return full_pattern.replace("\\", "/")


def find_previous_backup(dest_dir: Path) -> Path | None:
    candidates = [path for path in dest_dir.iterdir() if path.is_dir()]
    filtered: List[Path] = []
    for path in candidates:
        name = path.name
        if name.endswith("-inprogress") or name.endswith("-partial"):
            continue
        filtered.append(path)

    if not filtered:
        return None

    return sorted(filtered)[-1]


def remove_inprogress_dirs(dest_dir: Path) -> None:
    for entry in dest_dir.iterdir():
        if entry.is_dir() and (entry.name.endswith("-inprogress") or entry.name.endswith("-partial")):
            shutil.rmtree(entry)
            print(f"Removed unfinished snapshot: {entry}")


def build_rsync_command(
    source_dir: Path,
    destination: Path,
    link_dest: Path | None,
    filters: Iterable[FilterRule],
    extra_flags: Iterable[str] | None = None,
) -> List[str]:
    command = ["rsync", "-avz", "--delete"]

    if extra_flags:
        command.extend(extra_flags)
    for action, pattern in filters:
        command.append(f"--filter={action} {pattern}")

    if link_dest is not None:
        command.append(f"--link-dest={link_dest}")

    command.extend([f"{source_dir.as_posix()}/", destination.as_posix()])
    return command


def dry_run_has_changes(command: List[str]) -> bool:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        else:
            print("rsync dry-run failed", file=sys.stderr)
        raise SystemExit(result.returncode)

    noisy_prefixes = (
        "sending incremental file list",
        "sent ",
        "total size ",
        "delta-transmission ",
    )

    for line in (line.strip() for line in result.stdout.splitlines()):
        if not line or any(line.startswith(prefix) for prefix in noisy_prefixes):
            continue
        return True

    return False


def main() -> None:
    args = parse_args()
    source_dir = Path(args.source_dir).expanduser().resolve()
    dest_dir = Path(args.dest_dir).expanduser().resolve()

    if not source_dir.is_dir():
        print(f"Source directory does not exist: {source_dir}", file=sys.stderr)
        raise SystemExit(1)

    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    remove_inprogress_dirs(dest_dir)

    previous_backup = find_previous_backup(dest_dir)

    rules = gather_backupignore_rules(source_dir)
    for cli_pattern in args.exclude:
        if cli_pattern:
            rules.append(("-", cli_pattern))

    if previous_backup is not None:
        change_check_command = build_rsync_command(
            source_dir,
            previous_backup,
            None,
            rules,
            extra_flags=["--dry-run", "--itemize-changes"],
        )

        if not dry_run_has_changes(change_check_command):
            print("No changes detected since last backup; skipping new snapshot.")
            return

    inprogress_dir = dest_dir / f"{timestamp}-partial"
    final_dir = dest_dir / timestamp
    inprogress_dir.mkdir(parents=True, exist_ok=True)

    command = build_rsync_command(source_dir, inprogress_dir, previous_backup, rules)

    print(f"Running rsync to create snapshot: {inprogress_dir}")
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        else:
            print("rsync failed", file=sys.stderr)
        raise SystemExit(result.returncode)

    inprogress_dir.rename(final_dir)
    print(f"Snapshot created: {final_dir}")


if __name__ == "__main__":
    main()
