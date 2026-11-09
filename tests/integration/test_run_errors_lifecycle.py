from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.utils import REPO_ROOT, random_vm_name, require_host_tools, run_cli, run_cmd, write_config


pytestmark = pytest.mark.host_integration


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    require_host_tools()
    run_cli(["prepare", "--non-interactive"], check=True)


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


def test_run_selects_an_explicit_ambiguous_mount_on_a_real_vm(tmp_path: Path) -> None:
    source = REPO_ROOT / f".tmp-run-ambiguous-{random_vm_name('source')}"
    source.mkdir()
    (source / "file.txt").write_text("content", encoding="utf-8")
    vm_name = random_vm_name("it-run-ambiguous")
    first_target = "/home/ubuntu/project-first"
    second_target = "/home/ubuntu/project-second"
    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        {
            "vms": {vm_name: {"cpu": 1, "ram": "1G", "disk": "5G"}},
            "mounts": [
                {
                    "source": str(source),
                    "target": first_target,
                    "backup": str(tmp_path / "backups-first"),
                    "interval": 1,
                    "max_backups": 2,
                    "backup_clean_method": "tail",
                    "vm": vm_name,
                },
                {
                    "source": str(source),
                    "target": second_target,
                    "backup": str(tmp_path / "backups-second"),
                    "interval": 1,
                    "max_backups": 2,
                    "backup_clean_method": "tail",
                    "vm": vm_name,
                },
            ],
            "agents": {"local-bash": {"type": "custom", "command": "bash", "vm": vm_name}},
        },
    )
    try:
        run_cli(["create-vm", vm_name, "--config", str(config_path), "--non-interactive"], check=True)
        run_cmd(
            [
                "multipass",
                "exec",
                vm_name,
                "--",
                "bash",
                "-lc",
                f"sudo mkdir -p {first_target} {second_target}",
            ],
            check=True,
        )
        run_cmd(["multipass", "mount", str(source), f"{vm_name}:{first_target}"], check=True)
        run_cmd(["multipass", "mount", str(source), f"{vm_name}:{second_target}"], check=True)

        ambiguous = run_cli(
            ["run", "--config", str(config_path), "--workdir", str(source), "--non-interactive", "local-bash"],
            check=False,
        )
        output = (ambiguous.stderr or "") + (ambiguous.stdout or "")
        assert ambiguous.returncode != 0
        assert f"--vm {vm_name} --mount-target {first_target}" in output
        assert f"--vm {vm_name} --mount-target {second_target}" in output

        selected = run_cli(
            [
                "run",
                "--config",
                str(config_path),
                "--workdir",
                str(source),
                "--vm",
                vm_name,
                "--mount-target",
                second_target,
                "--disable-backups",
                "--no-first-backup",
                "--non-interactive",
                "local-bash",
                "-c",
                "pwd",
            ],
            check=True,
        )
        assert second_target in selected.stdout
    finally:
        run_cmd(["multipass", "delete", vm_name], check=False)
        run_cmd(["multipass", "purge"], check=False)
        if source.exists():
            (source / "file.txt").unlink(missing_ok=True)
            source.rmdir()
