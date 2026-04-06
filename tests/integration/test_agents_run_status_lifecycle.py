from __future__ import annotations

import pytest

from tests.integration.utils import (
    REPO_ROOT,
    random_vm_name,
    require_host_tools,
    run_cmd,
    run_cli,
    wait_for,
    write_config,
)


pytestmark = pytest.mark.host_integration


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    require_host_tools()
    run_cli(["prepare", "--non-interactive"], check=True)


@pytest.fixture(scope="module")
def agent_env(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("agent-run")
    base_dir = REPO_ROOT / f".tmp-agent-{random_vm_name('data')}"
    base_dir.mkdir(parents=True, exist_ok=True)
    source = base_dir / "source"
    source.mkdir()
    (source / "file.txt").write_text("content", encoding="utf-8")
    backup = base_dir / "backups"
    backup.mkdir()

    vm_name = random_vm_name("it-agent")
    config_path = tmp_path / "config.yaml"
    payload = {
        "vms": {
            vm_name: {
                "cpu": 1,
                "ram": "1G",
                "disk": "6G",
            }
        },
        "mounts": [
            {
                "source": str(source),
                "backup": str(backup),
                "interval": 1,
                "max_backups": 5,
                "backup_clean_method": "tail",
                "vm": vm_name,
            }
        ],
        "agents": {
            "aider-local": {
                "type": "aider",
                "vm": vm_name,
            },
            "qwen-local": {
                "type": "qwen",
                "vm": vm_name,
            },
            "forgecode-local": {
                "type": "forgecode",
                "vm": vm_name,
            },
            "codex-local": {
                "type": "codex",
                "vm": vm_name,
            },
        },
    }
    write_config(config_path, payload)
    run_cli(["create-vm", vm_name, "--config", str(config_path), "--non-interactive"], check=True)
    try:
        yield {
            "config_path": config_path,
            "vm_name": vm_name,
            "source": source,
            "backup": backup,
            "base_dir": base_dir,
        }
    finally:
        run_cmd(["multipass", "delete", vm_name], check=False)
        run_cmd(["multipass", "purge"], check=False)
        if base_dir.exists():
            for entry in base_dir.glob("**/*"):
                if entry.is_file():
                    entry.unlink(missing_ok=True)
            for entry in sorted(base_dir.glob("**/*"), reverse=True):
                if entry.is_dir():
                    entry.rmdir()
            base_dir.rmdir()


def test_install_agents_installs_binary(agent_env) -> None:
    config_path = agent_env["config_path"]
    vm_name = agent_env["vm_name"]
    run_cli(
        ["install-agents", "qwen-local", vm_name, "--config", str(config_path), "--non-interactive"],
        check=True,
    )
    run_cmd(
        ["multipass", "exec", vm_name, "--", "bash", "-lc", "command -v qwen >/dev/null"],
        check=True,
    )


def test_install_agents_installs_aider_binary(agent_env) -> None:
    config_path = agent_env["config_path"]
    vm_name = agent_env["vm_name"]
    run_cli(
        ["install-agents", "aider-local", vm_name, "--config", str(config_path), "--non-interactive"],
        check=True,
    )
    run_cmd(
        ["multipass", "exec", vm_name, "--", "bash", "-lc", "command -v aider >/dev/null"],
        check=True,
    )


def test_install_agents_installs_forgecode_binary(agent_env) -> None:
    config_path = agent_env["config_path"]
    vm_name = agent_env["vm_name"]
    run_cli(
        ["install-agents", "forgecode-local", vm_name, "--config", str(config_path), "--non-interactive"],
        check=True,
    )
    run_cmd(
        ["multipass", "exec", vm_name, "--", "bash", "-lc", "command -v forge >/dev/null"],
        check=True,
    )


def test_run_requires_auto_mount_when_missing(agent_env) -> None:
    config_path = agent_env["config_path"]
    source = agent_env["source"]
    result = run_cli(
        [
            "run",
            "--config",
            str(config_path),
            "--workdir",
            str(source),
            "--disable-backups",
            "--non-interactive",
            "qwen-local",
            "--help",
        ],
        check=False,
    )
    assert result.returncode != 0


def test_run_auto_mount_and_disable_backups(agent_env) -> None:
    config_path = agent_env["config_path"]
    source = agent_env["source"]
    backup = agent_env["backup"]
    if not source.exists():
        source.mkdir(parents=True, exist_ok=True)
        (source / "file.txt").write_text("content", encoding="utf-8")
    result = run_cli(
        [
            "run",
            "--config",
            str(config_path),
            "--workdir",
            str(source),
            "--disable-backups",
            "--auto-mount",
            "--non-interactive",
            "qwen-local",
            "--help",
        ],
        check=True,
    )
    assert result.returncode == 0
    assert not (backup / "backup.log").exists()
    assert not (backup / "backup.pid").exists()


def test_status_reports_running_agent(agent_env) -> None:
    config_path = agent_env["config_path"]
    vm_name = agent_env["vm_name"]
    result = run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            "nohup bash -lc 'exec -a codex sleep 60' >/tmp/codex.log 2>&1 & echo $!",
        ],
        check=True,
    )
    pid = result.stdout.strip()
    try:
        wait_for(
            lambda: bool(pid),
            timeout=10.0,
            message="failed to launch codex-named process",
        )
        status = run_cli(["status", "--config", str(config_path), "--non-interactive"], check=True)
        assert "codex" in status.stdout
    finally:
        if pid:
            run_cmd(["multipass", "exec", vm_name, "--", "bash", "-lc", f"kill {pid}"], check=False)


def test_ssh_executes_command(agent_env) -> None:
    config_path = agent_env["config_path"]
    vm_name = agent_env["vm_name"]
    result = run_cli(
        [
            "ssh",
            vm_name,
            "--config",
            str(config_path),
            "--",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "--",
            "echo",
            "ok",
        ],
        check=True,
    )
    assert "ok" in (result.stdout or "")
