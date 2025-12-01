import sys
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from agsekit_cli.commands import backup_repeated


def test_backup_repeated_command_invokes_loop(monkeypatch, tmp_path):
    source = tmp_path / "src"
    dest = tmp_path / "dst"

    calls = []

    def fake_repeated(src: Path, dst: Path, interval_minutes: int, extra_excludes):
        calls.append((src, dst, interval_minutes, tuple(extra_excludes)))

    monkeypatch.setattr(backup_repeated, "backup_repeated", fake_repeated)

    runner = CliRunner()
    result = runner.invoke(
        backup_repeated.backup_repeated_command,
        [
            "--source-dir",
            str(source),
            "--dest-dir",
            str(dest),
            "--interval",
            "7",
            "--exclude",
            "*.log",
            "--exclude",
            "cache/",
        ],
    )

    assert result.exit_code == 0
    assert calls == [(source.resolve(), dest.resolve(), 7, ("*.log", "cache/"))]


def test_backup_repeated_mount_command_uses_config(monkeypatch, tmp_path):
    mount_source = tmp_path / "data"
    mount_target = tmp_path / "target"
    backup_dir = tmp_path / "backups"

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
mounts:
  - source: {mount_source}
    target: {mount_target}
    backup: {backup_dir}
    interval: 9
""",
        encoding="utf-8",
    )

    calls = []

    def fake_repeated(src: Path, dst: Path, interval_minutes: int, **_):
        calls.append((src, dst, interval_minutes))

    monkeypatch.setattr(backup_repeated, "backup_repeated", fake_repeated)

    runner = CliRunner()
    result = runner.invoke(
        backup_repeated.backup_repeated_mount_command,
        ["--mount", str(mount_source), "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls == [(mount_source.resolve(), backup_dir.resolve(), 9)]


def test_backup_repeated_mount_command_errors_on_missing_mount(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("mounts: []\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        backup_repeated.backup_repeated_mount_command,
        ["--mount", str(tmp_path / "missing"), "--config", str(config_path)],
    )

    assert result.exit_code != 0
    assert "не найдено" in result.output


def test_backup_repeated_all_command_starts_threads(monkeypatch, tmp_path):
    source_one = tmp_path / "first"
    source_two = tmp_path / "second"
    backup_one = tmp_path / "b1"
    backup_two = tmp_path / "b2"

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
mounts:
  - source: {source_one}
    backup: {backup_one}
    interval: 3
  - source: {source_two}
    backup: {backup_two}
""",
        encoding="utf-8",
    )

    calls = []

    def fake_repeated(src: Path, dst: Path, interval_minutes: int, **_):
        calls.append((src, dst, interval_minutes))

    monkeypatch.setattr(backup_repeated, "backup_repeated", fake_repeated)

    runner = CliRunner()
    result = runner.invoke(
        backup_repeated.backup_repeated_all_command,
        ["--config", str(config_path)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert sorted(calls) == sorted(
        [
            (source_one.resolve(), backup_one.resolve(), 3),
            (source_two.resolve(), backup_two.resolve(), 5),
        ]
    )
    assert "Запущено 2 циклических бэкапов" in result.output
