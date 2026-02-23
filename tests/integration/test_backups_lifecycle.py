from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import pytest
import yaml


pytestmark = pytest.mark.host_integration

REPO_ROOT = Path(__file__).resolve().parents[2]


def _clean_env(overrides: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "PROXYCHAINS_CONF_FILE"):
        env.pop(key, None)
    if overrides:
        env.update(overrides)
    return env


def _run(
    command: list[str],
    check: bool = True,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    effective_env = _clean_env(env)
    return subprocess.run(command, check=check, text=True, capture_output=True, cwd=cwd, env=effective_env)


def _run_cli(args: list[str], check: bool = True, cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
    env = _clean_env({"AGSEKIT_LANG": "en"})
    command = [sys.executable, str(REPO_ROOT / "agsekit"), *args]
    return _run(command, check=check, cwd=cwd or REPO_ROOT, env=env)


def _start_cli(args: list[str], cwd: Optional[Path] = None) -> subprocess.Popen[str]:
    env = _clean_env({"AGSEKIT_LANG": "en"})
    command = [sys.executable, str(REPO_ROOT / "agsekit"), *args]
    return subprocess.Popen(
        command,
        cwd=cwd or REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _snapshot_dirs(dest_dir: Path) -> list[Path]:
    if not dest_dir.exists():
        return []
    return sorted(
        path
        for path in dest_dir.iterdir()
        if path.is_dir() and not path.name.endswith("-partial") and not path.name.endswith("-inprogress")
    )


def _wait_for(
    predicate: Callable[[], bool],
    timeout: float,
    message: str,
    interval: float = 0.2,
) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError(message)


def _stop_process_with_sigint(process: subprocess.Popen[str], timeout: float = 10.0) -> int:
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    return int(process.returncode or 0)


def _write_mounts_config(config_path: Path, mounts: list[dict[str, object]]) -> None:
    payload = {
        "vms": {
            "agent": {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            }
        },
        "mounts": mounts,
    }
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _seed_snapshot_dirs(backup_dir: Path, count: int, interval_minutes: int = 5) -> list[str]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    base = datetime(2024, 1, 1, 0, 0, 0)
    names: list[str] = []
    for index in range(count):
        name = (base + timedelta(minutes=index * interval_minutes)).strftime("%Y%m%d-%H%M%S")
        (backup_dir / name).mkdir(parents=True, exist_ok=True)
        names.append(name)
    return names


@pytest.fixture(autouse=True)
def require_rsync() -> None:
    if shutil.which("rsync") is None:
        pytest.skip("rsync is required for backup integration tests")


def test_backup_once_creates_hardlink_snapshot_and_skips_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    stable = source / "stable.txt"
    changing = source / "changing.txt"
    stable.write_text("stable-v1", encoding="utf-8")
    changing.write_text("changing-v1", encoding="utf-8")

    _run_cli(["backup-once", "--source-dir", str(source), "--dest-dir", str(dest), "--non-interactive"], check=True)

    first_snapshots = _snapshot_dirs(dest)
    assert len(first_snapshots) == 1
    first_snapshot = first_snapshots[0]
    first_stable_inode = (first_snapshot / "stable.txt").stat().st_ino
    first_changing_inode = (first_snapshot / "changing.txt").stat().st_ino

    second_run = _run_cli(
        ["backup-once", "--source-dir", str(source), "--dest-dir", str(dest), "--non-interactive"],
        check=True,
    )
    assert second_run.returncode == 0
    assert len(_snapshot_dirs(dest)) == 1

    time.sleep(1.1)
    changing.write_text("changing-v2", encoding="utf-8")
    _run_cli(["backup-once", "--source-dir", str(source), "--dest-dir", str(dest), "--non-interactive"], check=True)

    snapshots = _snapshot_dirs(dest)
    assert len(snapshots) == 2
    second_snapshot = snapshots[-1]
    second_stable_inode = (second_snapshot / "stable.txt").stat().st_ino
    second_changing_inode = (second_snapshot / "changing.txt").stat().st_ino

    assert second_stable_inode == first_stable_inode
    assert second_changing_inode != first_changing_inode


def test_backup_repeated_stops_on_sigint_and_keeps_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()
    (source / "file.txt").write_text("content", encoding="utf-8")

    process = _start_cli(
        [
            "backup-repeated",
            "--source-dir",
            str(source),
            "--dest-dir",
            str(dest),
            "--interval",
            "1",
            "--max-backups",
            "10",
            "--backup-clean-method",
            "thin",
            "--non-interactive",
        ]
    )
    try:
        _wait_for(lambda: len(_snapshot_dirs(dest)) >= 1, timeout=30.0, message="First repeated backup was not created")
        time.sleep(0.3)
        returncode = _stop_process_with_sigint(process)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert returncode in {0, 1, 130, -signal.SIGINT}
    assert len(_snapshot_dirs(dest)) >= 1


def test_backup_repeated_mount_uses_mount_entry_from_config(tmp_path: Path) -> None:
    source = tmp_path / "source"
    backup = tmp_path / "backups"
    source.mkdir()
    backup.mkdir()
    (source / "file.txt").write_text("mount-mode", encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    _write_mounts_config(
        config_path,
        [
            {
                "source": str(source),
                "backup": str(backup),
                "interval": 1,
                "max_backups": 10,
                "backup_clean_method": "thin",
                "vm": "agent",
            }
        ],
    )

    process = _start_cli(
        [
            "backup-repeated-mount",
            "--mount",
            str(source),
            "--config",
            str(config_path),
            "--non-interactive",
        ]
    )
    try:
        _wait_for(
            lambda: len(_snapshot_dirs(backup)) >= 1,
            timeout=30.0,
            message="backup-repeated-mount did not create snapshot",
        )
        time.sleep(0.3)
        returncode = _stop_process_with_sigint(process)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert returncode in {0, 1, 130, -signal.SIGINT}
    assert len(_snapshot_dirs(backup)) >= 1


def test_backup_repeated_all_starts_loops_for_all_mounts(tmp_path: Path) -> None:
    source_one = tmp_path / "source-one"
    source_two = tmp_path / "source-two"
    backup_one = tmp_path / "backup-one"
    backup_two = tmp_path / "backup-two"
    for path in (source_one, source_two, backup_one, backup_two):
        path.mkdir()
    (source_one / "one.txt").write_text("1", encoding="utf-8")
    (source_two / "two.txt").write_text("2", encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    _write_mounts_config(
        config_path,
        [
            {
                "source": str(source_one),
                "backup": str(backup_one),
                "interval": 1,
                "max_backups": 10,
                "backup_clean_method": "thin",
                "vm": "agent",
            },
            {
                "source": str(source_two),
                "backup": str(backup_two),
                "interval": 1,
                "max_backups": 10,
                "backup_clean_method": "thin",
                "vm": "agent",
            },
        ],
    )

    process = _start_cli(["backup-repeated-all", "--config", str(config_path), "--non-interactive"])
    try:
        _wait_for(
            lambda: len(_snapshot_dirs(backup_one)) >= 1 and len(_snapshot_dirs(backup_two)) >= 1,
            timeout=30.0,
            message="backup-repeated-all did not start all mount loops",
        )
        time.sleep(0.3)
        returncode = _stop_process_with_sigint(process)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert returncode in {0, 1, 130, -signal.SIGINT}
    assert len(_snapshot_dirs(backup_one)) >= 1
    assert len(_snapshot_dirs(backup_two)) >= 1


def test_backup_clean_tail_keeps_latest_snapshots(tmp_path: Path) -> None:
    source = tmp_path / "source"
    backup = tmp_path / "backups"
    source.mkdir()
    names = _seed_snapshot_dirs(backup, count=5, interval_minutes=5)

    config_path = tmp_path / "config.yaml"
    _write_mounts_config(
        config_path,
        [
            {
                "source": str(source),
                "backup": str(backup),
                "interval": 5,
                "max_backups": 10,
                "backup_clean_method": "tail",
                "vm": "agent",
            }
        ],
    )

    _run_cli(
        [
            "backup-clean",
            str(source),
            "2",
            "tail",
            "--config",
            str(config_path),
            "--non-interactive",
        ],
        check=True,
    )

    remaining = [path.name for path in _snapshot_dirs(backup)]
    assert remaining == names[-2:]


def test_backup_clean_thin_reduces_history_and_keeps_newest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    backup = tmp_path / "backups"
    source.mkdir()
    names = _seed_snapshot_dirs(backup, count=10, interval_minutes=5)

    config_path = tmp_path / "config.yaml"
    _write_mounts_config(
        config_path,
        [
            {
                "source": str(source),
                "backup": str(backup),
                "interval": 5,
                "max_backups": 10,
                "backup_clean_method": "thin",
                "vm": "agent",
            }
        ],
    )

    _run_cli(
        [
            "backup-clean",
            str(source),
            "4",
            "thin",
            "--config",
            str(config_path),
            "--non-interactive",
        ],
        check=True,
    )

    remaining = [path.name for path in _snapshot_dirs(backup)]
    assert len(remaining) == 4
    assert names[-1] in remaining
