import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agsekit_cli import backup


def test_backup_lock_waits_and_logs_on_conflict(monkeypatch, tmp_path):
    monkeypatch.setenv("AGSEKIT_LANG", "en")
    dest_dir = tmp_path / "backups"
    dest_dir.mkdir()
    (dest_dir / "backup.pid").write_text("12345", encoding="utf-8")

    attempts = {"count": 0}

    def fake_try_acquire(_handle):
        attempts["count"] += 1
        return attempts["count"] >= 2

    monkeypatch.setattr(backup, "_try_acquire_lock", fake_try_acquire)
    monkeypatch.setattr(backup, "_pid_is_ags_backup", lambda pid: True)

    logs = []
    sleeps = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    with backup.BackupLock(
        dest_dir,
        announce_wait=True,
        sleep_seconds=5,
        logger=logs.append,
        sleep_func=fake_sleep,
    ):
        pass

    assert logs
    assert "PID 12345" in logs[0]
    assert sleeps == [5]


def test_backup_lock_masks_non_ags_pid(monkeypatch, tmp_path):
    monkeypatch.setenv("AGSEKIT_LANG", "en")
    dest_dir = tmp_path / "backups"
    dest_dir.mkdir()
    (dest_dir / "backup.pid").write_text("99999", encoding="utf-8")

    attempts = {"count": 0}

    def fake_try_acquire(_handle):
        attempts["count"] += 1
        return attempts["count"] >= 2

    monkeypatch.setattr(backup, "_try_acquire_lock", fake_try_acquire)
    monkeypatch.setattr(backup, "_pid_is_ags_backup", lambda pid: False)

    logs = []

    def fake_sleep(_seconds: float) -> None:
        return None

    with backup.BackupLock(
        dest_dir,
        announce_wait=True,
        sleep_seconds=1,
        logger=logs.append,
        sleep_func=fake_sleep,
    ):
        pass

    assert logs
    assert "PID unknown" in logs[0]


def test_backup_repeated_honors_quiet_lock_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AGSEKIT_BACKUP_LOCK_QUIET", "1")
    source_dir = tmp_path / "src"
    dest_dir = tmp_path / "dst"

    seen = []

    class DummyLock:
        def __init__(self, _dest_dir, *, announce_wait=True, **kwargs):
            seen.append(announce_wait)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

    monkeypatch.setattr(backup, "BackupLock", DummyLock)
    monkeypatch.setattr(backup, "backup_once", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(backup, "clean_backups", lambda *_args, **_kwargs: [])

    backup.backup_repeated(
        source_dir,
        dest_dir,
        interval_minutes=1,
        sleep_func=lambda _seconds: None,
        max_runs=1,
    )

    assert seen == [False]


def test_try_acquire_lock_uses_portalocker(monkeypatch, tmp_path):
    lock_path = tmp_path / "backup.pid"
    handle = lock_path.open("a+", encoding="utf-8")
    calls = []

    def fake_lock(received_handle, flags):
        calls.append((received_handle, flags))

    monkeypatch.setattr(backup.portalocker, "lock", fake_lock)

    try:
        assert backup._try_acquire_lock(handle) is True
    finally:
        handle.close()

    assert calls == [
        (
            handle,
            backup.portalocker.LockFlags.EXCLUSIVE | backup.portalocker.LockFlags.NON_BLOCKING,
        )
    ]


def test_try_acquire_lock_returns_false_on_portalocker_conflict(monkeypatch, tmp_path):
    lock_path = tmp_path / "backup.pid"
    handle = lock_path.open("a+", encoding="utf-8")

    def fake_lock(_handle, _flags):
        raise backup.portalocker.LockException()

    monkeypatch.setattr(backup.portalocker, "lock", fake_lock)

    try:
        assert backup._try_acquire_lock(handle) is False
    finally:
        handle.close()


def test_backup_lock_sleep_seconds_env_override(monkeypatch):
    monkeypatch.setenv(backup.BACKUP_LOCK_SLEEP_ENV_VAR, "0.25")

    assert backup._backup_lock_sleep_seconds() == 0.25


def test_backup_lock_sleep_seconds_env_invalid_falls_back(monkeypatch):
    monkeypatch.setenv(backup.BACKUP_LOCK_SLEEP_ENV_VAR, "invalid")

    assert backup._backup_lock_sleep_seconds() == backup.DEFAULT_BACKUP_LOCK_SLEEP_SECONDS


def test_pid_is_ags_backup_uses_psutil_cmdline(monkeypatch):
    class DummyProcess:
        def __init__(self, pid):
            self.pid = pid

        def cmdline(self):
            return ["python", "-m", "agsekit", "backup-repeated"]

    monkeypatch.setattr(backup.psutil, "Process", DummyProcess)

    assert backup._pid_is_ags_backup(12345) is True


def test_pid_is_ags_backup_returns_false_on_psutil_error(monkeypatch):
    def fake_process(_pid):
        raise backup.psutil.NoSuchProcess(pid=12345)

    monkeypatch.setattr(backup.psutil, "Process", fake_process)

    assert backup._pid_is_ags_backup(12345) is False
