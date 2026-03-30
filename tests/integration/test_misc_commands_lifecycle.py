from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.utils import (
    REPO_ROOT,
    random_vm_name,
    require_host_tools,
    run_cli,
    run_process,
    write_config,
)


pytestmark = pytest.mark.host_integration


def test_config_example_and_gen(tmp_path: Path) -> None:
    example_path = tmp_path / "config-example.yaml"
    run_cli(["config-example", str(example_path)], check=True, cwd=tmp_path)
    assert example_path.exists()

    generated_path = tmp_path / "config-gen.yaml"
    input_script = "\n".join(
        [
            "",  # global ssh_keys_folder default
            "",  # global systemd_env_folder default
            "",  # global portforward interval default
            "",  # vm name default
            "",  # cpu default
            "",  # ram default
            "",  # disk default
            "",  # proxychains empty
            "",  # allowed agents empty
            "",  # cloud-init path empty
            "",  # add more vms? default no
            "n",  # add mount? no
            "",  # add agent? default no
            str(generated_path),  # destination
        ]
    )
    result = run_process(
        [
            sys.executable,
            str(REPO_ROOT / "agsekit"),
            "config-gen",
            "--config",
            str(generated_path),
            "--non-interactive",
        ],
        cwd=tmp_path,
        check=True,
        input_text=input_script,
    )
    assert generated_path.exists(), result.stderr


def test_list_bundles_and_version() -> None:
    bundles = run_cli(["list-bundles"], check=True)
    assert "docker" in bundles.stdout

    version = run_cli(["version"], check=True)
    assert version.stdout.strip()


def test_pip_upgrade_runs() -> None:
    result = run_cli(["pip-upgrade"], check=True)
    assert result.returncode == 0


def test_shell_requires_vm_when_multiple(tmp_path: Path) -> None:
    vm_one = random_vm_name("it-shell")
    vm_two = random_vm_name("it-shell")
    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        {
            "vms": {
                vm_one: {"cpu": 1, "ram": "1G", "disk": "5G"},
                vm_two: {"cpu": 1, "ram": "1G", "disk": "5G"},
            }
        },
    )
    result = run_cli(["shell", "--config", str(config_path), "--non-interactive"], check=False)
    assert result.returncode != 0


def test_doctor_smoke(tmp_path: Path) -> None:
    require_host_tools()
    run_cli(["prepare", "--non-interactive"], check=True)
    vm_name = random_vm_name("it-doctor")
    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        {
            "vms": {
                vm_name: {"cpu": 1, "ram": "1G", "disk": "5G"},
            }
        },
    )
    run_cli(["doctor", "--config", str(config_path), "--non-interactive"], check=True)
