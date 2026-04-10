import io
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.backup as backup


def test_backup_once_uses_progress_flags(monkeypatch, tmp_path):
    source = tmp_path / "src"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    calls: dict[str, object] = {}

    def fake_run(command: List[str], *, show_progress: bool):
        calls["command"] = command
        calls["show_progress"] = show_progress
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(backup, "_run_rsync", fake_run)
    monkeypatch.setattr(backup, "remove_inprogress_dirs", lambda *_: None)
    monkeypatch.setattr(backup, "find_previous_backup", lambda *_: None)
    monkeypatch.setattr(backup.platform, "system", lambda: "Linux")

    backup.backup_once(source, dest, show_progress=True)

    assert "--progress" in calls["command"]
    assert "--info=progress2" in calls["command"]
    assert calls["show_progress"] is True


def test_rsync_progress_flags_are_platform_specific():
    assert backup.rsync_progress_flags("Linux") == ["--progress", "--info=progress2"]
    assert backup.rsync_progress_flags("Darwin") == ["--progress"]
    assert backup.rsync_progress_flags("Windows") == ["--progress"]


def test_run_rsync_renders_progress_bar(monkeypatch, capsys):
    stdout = io.StringIO("123  10%    0:00:01\n456  45%    0:00:02\n999 100%    0:00:03\n")
    stderr = io.StringIO("")
    popen_kwargs: dict[str, object] = {}

    class DummyProcess:
        def __init__(self):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = 0

        def wait(self):
            return self.returncode

    def fake_popen(*args, **kwargs):
        popen_kwargs.update(kwargs)
        return DummyProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    result = backup._run_rsync(["rsync"], show_progress=True)

    output = capsys.readouterr().out
    assert "Progress: [" in output
    assert output.strip().endswith("100%")
    assert popen_kwargs["errors"] == "replace"
    assert result.returncode == 0


def test_run_rsync_without_progress_replaces_decode_errors(monkeypatch):
    run_kwargs: dict[str, object] = {}

    def fake_run(command: List[str], **kwargs):
        run_kwargs.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = backup._run_rsync(["rsync"], show_progress=False)

    assert result.returncode == 0
    assert run_kwargs["errors"] == "replace"


def test_run_rsync_progress_tolerates_non_utf8_output():
    command = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.buffer.write(b'file:\\xd0\\n100%\\n')",
    ]

    result = backup._run_rsync(command, show_progress=True)

    assert result.returncode == 0
    assert "\ufffd" in result.stdout


def test_run_rsync_reports_real_progress(tmp_path, capsys):
    if shutil.which("rsync") is None:
        pytest.skip("rsync is required for this test")

    source = tmp_path / "src"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    payload = b"a" * 1024 * 1024
    (source / "sample.bin").write_bytes(payload)

    command = backup.build_rsync_command(
        source,
        dest,
        None,
        [],
        extra_flags=backup.rsync_progress_flags(),
    )

    result = backup._run_rsync(command, show_progress=True)
    progress_output = capsys.readouterr().out

    percent_values = [backup._extract_progress_percentage(line) for line in result.stdout.splitlines()]

    assert result.returncode == 0
    assert (dest / "sample.bin").read_bytes() == payload
    assert any(percent is not None for percent in percent_values)
    assert "Progress: [" in progress_output
    assert progress_output.strip().endswith("100%")


def test_backup_once_continues_on_rsync_warning(monkeypatch, tmp_path, capsys):
    source = tmp_path / "src"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()
    (source / "file.txt").write_text("data", encoding="utf-8")

    def fake_run(command: List[str], *, show_progress: bool):
        return subprocess.CompletedProcess(command, 23, stdout="", stderr="rsync: opendir permission denied")

    monkeypatch.setattr(backup, "_run_rsync", fake_run)
    monkeypatch.setattr(backup, "remove_inprogress_dirs", lambda *_: None)
    monkeypatch.setattr(backup, "find_previous_backup", lambda *_: None)

    backup.backup_once(source, dest)

    stderr = capsys.readouterr().err
    assert "rsync completed with warnings" in stderr
    assert "permission denied" in stderr
    snapshots = [path for path in dest.iterdir() if path.is_dir()]
    assert len(snapshots) == 1
