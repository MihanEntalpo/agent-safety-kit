from __future__ import annotations

import pytest

import agsekit_cli.vm as vm_module
from agsekit_cli.config import VmConfig


def _result(*, returncode: int = 0, stdout: str = "", stderr: str = ""):
    class Result:
        pass

    result = Result()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def _vm(name: str = "agent-vm") -> VmConfig:
    return VmConfig(name=name, cpu=1, ram="1G", disk="5G", cloud_init={}, port_forwarding=[])


def test_ensure_proxychains_runner_uploads_scripts_via_stdin(monkeypatch):
    calls: list[tuple[list[str], str | None]] = []

    def fake_run(command, check=False, capture_output=False, text=False, input=None):
        calls.append((command, input))
        return _result()

    monkeypatch.setattr(vm_module.subprocess, "run", fake_run)

    runner_path = vm_module.ensure_proxychains_runner(_vm())

    assert runner_path == vm_module.PROXYCHAINS_RUNNER_REMOTE
    assert [cmd for cmd, _ in calls] == [
        ["multipass", "exec", "agent-vm", "--", "mkdir", "-p", vm_module.PROXYCHAINS_HELPER_REMOTE_DIR],
        [
            "multipass",
            "exec",
            "agent-vm",
            "--",
            "bash",
            "-lc",
            f"cat > {vm_module.PROXYCHAINS_HELPER_REMOTE}",
        ],
        [
            "multipass",
            "exec",
            "agent-vm",
            "--",
            "bash",
            "-lc",
            f"cat > {vm_module.PROXYCHAINS_RUNNER_REMOTE}",
        ],
        ["multipass", "exec", "agent-vm", "--", "chmod", "+x", vm_module.PROXYCHAINS_RUNNER_REMOTE],
    ]
    helper_payload = calls[1][1]
    runner_payload = calls[2][1]
    assert isinstance(helper_payload, str)
    assert isinstance(runner_payload, str)
    assert "build_proxychains_config" in helper_payload
    assert "proxychains4" in runner_payload


def test_ensure_proxychains_runner_fails_when_stdin_upload_fails(monkeypatch):
    def fake_run(command, check=False, capture_output=False, text=False, input=None):
        if command[:3] == ["multipass", "exec", "agent-vm"] and command[4:7] == ["bash", "-lc", f"cat > {vm_module.PROXYCHAINS_HELPER_REMOTE}"]:
            return _result(returncode=2, stderr="permission denied")
        return _result()

    monkeypatch.setattr(vm_module.subprocess, "run", fake_run)

    with pytest.raises(vm_module.MultipassError, match="Failed to transfer proxychains helper"):
        vm_module.ensure_proxychains_runner(_vm())
