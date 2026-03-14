from __future__ import annotations

import time
from pathlib import Path

import pytest

from tests.integration.utils import run_cli, write_config


pytestmark = pytest.mark.host_integration


def _list_snapshots(dest: Path) -> list[Path]:
    if not dest.exists():
        return []
    return sorted(
        path
        for path in dest.iterdir()
        if path.is_dir() and not path.name.endswith("-partial") and not path.name.endswith("-inprogress")
    )


def test_backup_clean_tail_removes_old_snapshots(tmp_path: Path) -> None:
    source = tmp_path / "source"
    backup = tmp_path / "backups"
    source.mkdir()
    backup.mkdir()
    (source / "file.txt").write_text("v1", encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        {
            "vms": {"vm": {"cpu": 1, "ram": "1G", "disk": "5G"}},
            "mounts": [
                {
                    "source": str(source),
                    "backup": str(backup),
                    "interval": 1,
                    "max_backups": 5,
                    "backup_clean_method": "tail",
                    "vm": "vm",
                }
            ],
        },
    )

    run_cli(
        ["backup-once", "--source-dir", str(source), "--dest-dir", str(backup), "--non-interactive"],
        check=True,
    )
    time.sleep(1.1)
    (source / "file.txt").write_text("v2", encoding="utf-8")
    run_cli(
        ["backup-once", "--source-dir", str(source), "--dest-dir", str(backup), "--non-interactive"],
        check=True,
    )

    assert len(_list_snapshots(backup)) == 2

    run_cli(
        ["backup-clean", str(source), "1", "tail", "--config", str(config_path), "--non-interactive"],
        check=True,
    )

    snapshots = _list_snapshots(backup)
    assert len(snapshots) == 1
