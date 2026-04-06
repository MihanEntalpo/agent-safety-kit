from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.utils import REPO_ROOT, random_vm_name, run_cli, write_config


pytestmark = pytest.mark.host_integration


def test_run_reports_missing_workdir(tmp_path: Path) -> None:
    missing = REPO_ROOT / f".missing-{random_vm_name('run')}"
    if missing.exists():
        missing.rmdir()

    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        {
            "vms": {
                "agent": {"cpu": 1, "ram": "1G", "disk": "5G"},
            },
            "agents": {
                "qwen": {"type": "qwen", "vm": "agent"},
            },
        },
    )

    result = run_cli(
        ["run", "--config", str(config_path), "--workdir", str(missing), "--non-interactive", "qwen", "--help"],
        check=False,
    )
    output = (result.stderr or "") + (result.stdout or "")
    assert "Working directory does not exist" in output
    assert str(missing.resolve()) in output
