from __future__ import annotations

import os
import sys
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import log2
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from .i18n import tr

FilterRule = Tuple[str, str]


@dataclass(frozen=True)
class ThinParams:
    interval_minutes: int = 5
    protect_newest_k: int = 3
    max_intervals_space: int = 288


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


def list_backup_snapshots(dest_dir: Path) -> List[Path]:
    if not dest_dir.exists():
        return []

    candidates = [path for path in dest_dir.iterdir() if path.is_dir()]
    filtered: List[Path] = []
    for path in candidates:
        name = path.name
        if name.endswith("-inprogress") or name.endswith("-partial"):
            continue
        filtered.append(path)

    return sorted(filtered)


def clean_backups_tail(dest_dir: Path, keep: int) -> List[Path]:
    if keep < 0:
        raise ValueError("keep must be non-negative")

    snapshots = list_backup_snapshots(dest_dir)
    if keep >= len(snapshots):
        return []

    to_remove = snapshots[: len(snapshots) - keep]
    for path in to_remove:
        shutil.rmtree(path)

    return to_remove


def _snapshot_datetime(snapshot: Path) -> datetime:
    try:
        return datetime.strptime(snapshot.name, "%Y%m%d-%H%M%S")
    except ValueError:
        return datetime.fromtimestamp(snapshot.stat().st_mtime)


def _bucket_id(age_minutes: float, interval_minutes: int) -> int:
    if age_minutes <= 0:
        return -1
    ratio = max(1.0, age_minutes / float(interval_minutes))
    return max(0, int(log2(ratio)))


def _bucket_target(bucket_id: int) -> int:
    if bucket_id <= 0:
        return 3
    if bucket_id == 1:
        return 2
    return 1


def _choose_thin_deletion(times: List[datetime], params: ThinParams, keep: int) -> int:
    count = len(times)
    if count <= 1:
        return 0

    base_gap = timedelta(minutes=params.interval_minutes)
    max_gap = base_gap * params.max_intervals_space

    for older, newer in zip(times, times[1:]):
        if (newer - older) > max_gap:
            return 0

    newest = times[-1]
    protect_count = min(params.protect_newest_k, keep, count)
    protected: Set[int] = set(range(count - protect_count, count))
    candidates_idx = [i for i in range(count) if i not in protected and i != (count - 1)]
    if not candidates_idx:
        return 0

    buckets: Dict[int, List[int]] = {}
    for idx in candidates_idx:
        age_min = (newest - times[idx]).total_seconds() / 60.0
        bucket = _bucket_id(age_min, params.interval_minutes)
        buckets.setdefault(bucket, []).append(idx)

    overflow: List[Tuple[float, int]] = []
    for bucket, idxs in buckets.items():
        target = _bucket_target(bucket)
        ratio = len(idxs) / float(target)
        if ratio > 1.0:
            overflow.append((ratio, bucket))

    def damage(idx: int) -> Tuple[timedelta, timedelta, datetime]:
        if idx == 0:
            gap = times[1] - times[0]
            return (gap + gap, gap, times[idx])
        if idx == count - 1:
            gap = times[idx] - times[idx - 1]
            return (gap + gap, gap, times[idx])

        left = times[idx] - times[idx - 1]
        right = times[idx + 1] - times[idx]
        return (left + right, max(left, right), times[idx])

    if overflow:
        overflow.sort(key=lambda item: (-item[0], -item[1]))
        bucket = overflow[0][1]
        idxs = buckets[bucket]
        idxs.sort(key=damage)
        return idxs[0]

    candidates_idx.sort(key=damage)
    return candidates_idx[0]


def clean_backups_thin(dest_dir: Path, keep: int, interval_minutes: int) -> List[Path]:
    if keep < 0:
        raise ValueError("keep must be non-negative")

    snapshots = list_backup_snapshots(dest_dir)
    if keep >= len(snapshots):
        return []

    entries = [(_snapshot_datetime(snapshot), snapshot) for snapshot in snapshots]
    entries.sort(key=lambda item: (item[0], item[1].name))
    removed: List[Path] = []
    params = ThinParams(interval_minutes=interval_minutes)

    while len(entries) > keep:
        times = [entry[0] for entry in entries]
        idx = _choose_thin_deletion(times, params, keep)
        path = entries[idx][1]
        shutil.rmtree(path)
        removed.append(path)
        del entries[idx]

    return removed


def clean_backups(dest_dir: Path, keep: int, method: str, *, interval_minutes: int = 5) -> List[Path]:
    method = method.lower()
    if method not in {"tail", "thin"}:
        raise ValueError(tr("backup.clean_method_unknown", method=method))

    if not dest_dir.exists():
        return []

    if method == "thin":
        return clean_backups_thin(dest_dir, keep, interval_minutes)

    return clean_backups_tail(dest_dir, keep)


def remove_inprogress_dirs(dest_dir: Path) -> None:
    for entry in dest_dir.iterdir():
        if entry.is_dir() and (entry.name.endswith("-inprogress") or entry.name.endswith("-partial")):
            shutil.rmtree(entry)
            print(tr("backup.removed_unfinished_snapshot", path=entry))


def write_inode_snapshot(snapshot_dir: Path) -> None:
    inodes_path = snapshot_dir / ".inodes"
    inodes_path.touch(exist_ok=True)

    entries: List[Tuple[str, int]] = []
    for dirpath, _dirnames, filenames in os.walk(snapshot_dir):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            rel_path = file_path.relative_to(snapshot_dir).as_posix()
            inode = file_path.lstat().st_ino
            entries.append((rel_path, inode))

    entries.sort(key=lambda item: item[0])

    with inodes_path.open("w", encoding="utf-8", errors="surrogateescape") as handle:
        for rel_path, inode in entries:
            handle.write(f"{rel_path} {inode}\n")


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
    print(tr("backup.progress_bar", bar=bar, percent=percent), end="", flush=True)


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


def _is_rsync_warning(returncode: int) -> bool:
    return returncode in {23, 24}


def dry_run_has_changes(command: List[str]) -> bool:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        else:
            print(tr("backup.rsync_dry_run_failed"), file=sys.stderr)
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
        if ".inodes" in line and "deleting" in line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            flags, path = parts
            if flags.startswith(".d") and path.endswith("/"):
                continue
        return True

    return False


def backup_once(
    source_dir: Path, dest_dir: Path, extra_excludes: Optional[Iterable[str]] = None, *, show_progress: bool = False
) -> None:
    source_dir = source_dir.expanduser().resolve()
    dest_dir = dest_dir.expanduser().resolve()

    if not source_dir.is_dir():
        print(tr("backup.source_dir_missing", path=source_dir), file=sys.stderr)
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
            print(tr("backup.no_changes_detected"))
            return

    inprogress_dir = dest_dir / f"{timestamp}-partial"
    final_dir = dest_dir / timestamp
    inprogress_dir.mkdir(parents=True, exist_ok=True)
    time.sleep(0.1)

    extra_flags = ["--progress", "--info=progress2"] if show_progress else None
    command = build_rsync_command(source_dir, inprogress_dir, previous_backup, rules, extra_flags=extra_flags)

    print(tr("backup.rsync_running", path=inprogress_dir))
    result = _run_rsync(command, show_progress=show_progress)
    if result.returncode != 0:
        if _is_rsync_warning(result.returncode):
            print(tr("backup.rsync_warning", code=result.returncode), file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        else:
            if result.stderr:
                print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
            else:
                print(tr("backup.rsync_failed"), file=sys.stderr)
            raise SystemExit(result.returncode)

    inprogress_dir.rename(final_dir)
    print(tr("backup.snapshot_created", path=final_dir))
    write_inode_snapshot(final_dir)


def backup_repeated(
    source_dir: Path,
    dest_dir: Path,
    *,
    interval_minutes: int = 5,
    max_backups: int = 100,
    backup_clean_method: str = "tail",
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
        raise ValueError(tr("backup.interval_positive_required"))
    if max_backups <= 0:
        raise ValueError(tr("backup.keep_positive_required"))

    runs_completed = 0
    first_cycle = True
    while True:
        if skip_first and first_cycle:
            first_cycle = False
            sleep_func(interval_minutes * 60)
            continue

        backup_once(source_dir, dest_dir, extra_excludes=extra_excludes)
        clean_backups(dest_dir, max_backups, backup_clean_method, interval_minutes=interval_minutes)
        first_cycle = False
        runs_completed += 1
        print(tr("backup.waiting_minutes", minutes=interval_minutes))

        if max_runs is not None and runs_completed >= max_runs:
            return

        sleep_func(interval_minutes * 60)
