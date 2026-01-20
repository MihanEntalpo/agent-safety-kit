import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from agsekit_cli import backup


def test_backup_repeated_runs_immediately_and_respects_interval(monkeypatch, capsys):
    calls = []
    clean_calls = []

    def fake_backup_once(source_dir: Path, dest_dir: Path, extra_excludes=None):
        calls.append((source_dir, dest_dir, tuple(extra_excludes or ())))

    def fake_clean_backups(dest_dir: Path, keep: int, method: str, *, interval_minutes: int = 5):
        clean_calls.append((dest_dir, keep, method, interval_minutes))
        return []

    sleep_calls = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(backup, "backup_once", fake_backup_once)
    monkeypatch.setattr(backup, "clean_backups", fake_clean_backups)

    backup.backup_repeated(
        Path("/src"),
        Path("/dst"),
        interval_minutes=2,
        extra_excludes=["*.log"],
        sleep_func=fake_sleep,
        max_runs=2,
    )

    assert calls == [
        (Path("/src"), Path("/dst"), ("*.log",)),
        (Path("/src"), Path("/dst"), ("*.log",)),
    ]
    assert clean_calls == [
        (Path("/dst"), 100, "tail", 2),
        (Path("/dst"), 100, "tail", 2),
    ]
    assert sleep_calls == [120]

    output = capsys.readouterr().out
    assert output.count("Done, waiting 2 minutes") == 2


def test_backup_repeated_can_skip_first(monkeypatch, capsys):
    calls = []
    clean_calls = []

    def fake_backup_once(source_dir: Path, dest_dir: Path, extra_excludes=None):
        calls.append((source_dir, dest_dir, tuple(extra_excludes or ())))

    def fake_clean_backups(dest_dir: Path, keep: int, method: str, *, interval_minutes: int = 5):
        clean_calls.append((dest_dir, keep, method, interval_minutes))
        return []

    sleep_calls = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(backup, "backup_once", fake_backup_once)
    monkeypatch.setattr(backup, "clean_backups", fake_clean_backups)

    backup.backup_repeated(
        Path("/src"),
        Path("/dst"),
        interval_minutes=2,
        sleep_func=fake_sleep,
        max_runs=1,
        skip_first=True,
    )

    assert calls == [(Path("/src"), Path("/dst"), ())]
    assert clean_calls == [(Path("/dst"), 100, "tail", 2)]
    assert sleep_calls == [120]
    assert "Done, waiting 2 minutes" in capsys.readouterr().out


def test_backup_repeated_requires_positive_interval():
    with pytest.raises(ValueError):
        backup.backup_repeated(Path("/a"), Path("/b"), interval_minutes=0, max_runs=1)
