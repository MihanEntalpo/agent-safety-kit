import sys
from datetime import datetime, timedelta
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agsekit_cli.commands import backup_clean


def _write_config(config_path: Path, mount_source: Path, backup_dir: Path) -> None:
    config_path.write_text(
        f"""
vms:
  agent:
    cpu: 1
    ram: 1G
    disk: 5G
mounts:
  - source: {mount_source}
    backup: {backup_dir}
""",
        encoding="utf-8",
    )


def test_backup_clean_tail_removes_old_snapshots(tmp_path: Path) -> None:
    mount_source = tmp_path / "data"
    mount_source.mkdir()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    snapshots = ["20240101-000001", "20240102-000001", "20240103-000001"]
    for name in snapshots:
        (backup_dir / name).mkdir()

    config_path = tmp_path / "config.yaml"
    _write_config(config_path, mount_source, backup_dir)

    runner = CliRunner()
    result = runner.invoke(
        backup_clean.backup_clean_command,
        ["--config", str(config_path), str(mount_source), "2", "tail"],
    )

    assert result.exit_code == 0
    assert (backup_dir / snapshots[0]).exists() is False
    assert (backup_dir / snapshots[1]).exists() is True
    assert (backup_dir / snapshots[2]).exists() is True
    assert str(backup_dir / snapshots[0]) in result.output


def test_backup_clean_thin_removes_snapshots(tmp_path: Path) -> None:
    mount_source = tmp_path / "data"
    mount_source.mkdir()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    snapshots = []
    base_dt = datetime(2024, 1, 1, 0, 0, 0)
    for idx in range(8):
        name = (base_dt + timedelta(minutes=5 * idx)).strftime("%Y%m%d-%H%M%S")
        snapshots.append(name)
        (backup_dir / name).mkdir()

    config_path = tmp_path / "config.yaml"
    _write_config(config_path, mount_source, backup_dir)

    runner = CliRunner()
    result = runner.invoke(
        backup_clean.backup_clean_command,
        ["--config", str(config_path), str(mount_source), "4", "thin"],
    )

    assert result.exit_code == 0
    assert sum(1 for _ in backup_dir.iterdir()) == 4
    assert (backup_dir / snapshots[-1]).exists()
    assert (backup_dir / snapshots[-2]).exists()
    assert (backup_dir / snapshots[-3]).exists()
    assert result.output.count("Removed snapshot") == 4


def test_backup_clean_errors_on_missing_mount(tmp_path: Path) -> None:
    mount_source = tmp_path / "data"
    backup_dir = tmp_path / "backups"

    config_path = tmp_path / "config.yaml"
    _write_config(config_path, mount_source, backup_dir)

    runner = CliRunner()
    result = runner.invoke(
        backup_clean.backup_clean_command,
        ["--config", str(config_path), str(tmp_path / "missing"), "10", "tail"],
    )

    assert result.exit_code != 0
    assert "is not defined" in result.output or "не найден" in result.output
