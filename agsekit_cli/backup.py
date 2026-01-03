from __future__ import annotations

import os
import sys
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

FilterRule = Tuple[str, str]


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


def find_previous_backup(dest_dir: Path) -> Optional[Path]:
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
    link_dest: Optional[Path],
    filters: Iterable[FilterRule],
    extra_flags: Optional[Iterable[str]] = None,
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


def _extract_progress_percentage(line: str) -> Optional[int]:
    for chunk in line.split():
        if not chunk.endswith("%"):
            continue
        numeric = chunk.rstrip("%")
        if numeric.isdigit():
            percent = int(numeric)
            if 0 <= percent <= 100:
                return percent
    return None


def _render_progress_bar(percent: int) -> None:
    percent = max(0, min(100, percent))
    bar_width = 30
    filled = int(bar_width * percent / 100)
    bar = "#" * filled + "-" * (bar_width - filled)
    print(f"\rProgress: [{bar}] {percent}%", end="", flush=True)


def _run_rsync(command: List[str], *, show_progress: bool) -> subprocess.CompletedProcess[str]:
    if not show_progress:
        return subprocess.run(command, check=False, capture_output=True, text=True)

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    stdout_chunks: List[str] = []
    stderr_chunks: List[str] = []
    last_percent = None

    try:
        if process.stdout:
            for line in process.stdout:
                stdout_chunks.append(line)
                progress = _extract_progress_percentage(line)
                if progress is not None and progress != last_percent:
                    _render_progress_bar(progress)
                    last_percent = progress

        if process.stderr:
            stderr_chunks.append(process.stderr.read())

        process.wait()
    finally:
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

    if last_percent is not None:
        print()

    return subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout="".join(stdout_chunks),
        stderr="".join(stderr_chunks),
    )


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


def backup_once(
    source_dir: Path, dest_dir: Path, extra_excludes: Optional[Iterable[str]] = None, *, show_progress: bool = False
) -> None:
    source_dir = source_dir.expanduser().resolve()
    dest_dir = dest_dir.expanduser().resolve()

    if not source_dir.is_dir():
        print(f"Source directory does not exist: {source_dir}", file=sys.stderr)
        raise SystemExit(1)

    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    remove_inprogress_dirs(dest_dir)

    previous_backup = find_previous_backup(dest_dir)

    rules = gather_backupignore_rules(source_dir)
    for cli_pattern in extra_excludes or []:
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
    time.sleep(0.1)

    extra_flags = ["--progress", "--info=progress2"] if show_progress else None
    command = build_rsync_command(source_dir, inprogress_dir, previous_backup, rules, extra_flags=extra_flags)

    print(f"Running rsync to create snapshot: {inprogress_dir}")
    result = _run_rsync(command, show_progress=show_progress)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        else:
            print("rsync failed", file=sys.stderr)
        raise SystemExit(result.returncode)

    inprogress_dir.rename(final_dir)
    print(f"Snapshot created: {final_dir}")


def backup_repeated(
    source_dir: Path,
    dest_dir: Path,
    *,
    interval_minutes: int = 5,
    extra_excludes: Optional[Iterable[str]] = None,
    sleep_func: Callable[[float], None] = time.sleep,
    max_runs: Optional[int] = None,
    skip_first: bool = False,
) -> None:
    """Run backups in a loop with the given interval.

    The function starts with an immediate backup and then repeats it every
    ``interval_minutes``. ``sleep_func`` and ``max_runs`` are provided to
    simplify testing and should not be customized in normal usage.
    """

    if interval_minutes <= 0:
        raise ValueError("Interval must be greater than zero minutes")

    runs_completed = 0
    first_cycle = True
    while True:
        if skip_first and first_cycle:
            first_cycle = False
            sleep_func(interval_minutes * 60)
            continue

        backup_once(source_dir, dest_dir, extra_excludes=extra_excludes)
        first_cycle = False
        runs_completed += 1
        print(f"Done, waiting {interval_minutes} minutes")

        if max_runs is not None and runs_completed >= max_runs:
            return

        sleep_func(interval_minutes * 60)
