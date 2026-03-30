from __future__ import annotations

import subprocess

import pytest

import agsekit_cli.vm as vm_module
from agsekit_cli.config import VmConfig


def _sample_vm(name: str = "agent-vm") -> VmConfig:
    return VmConfig(
        name=name,
        cpu=1,
        ram="1G",
        disk="5G",
        cloud_init={},
        port_forwarding=[],
    )


def test_build_launch_command_omits_timeout_by_default():
    command = vm_module._build_launch_command(_sample_vm(), None)

    assert command == [
        "multipass",
        "launch",
        "--name",
        "agent-vm",
        "--cpus",
        "1",
        "--memory",
        "1G",
        "--disk",
        "5G",
    ]


def test_build_launch_command_includes_timeout_when_requested():
    command = vm_module._build_launch_command(_sample_vm(), None, launch_timeout_seconds=600)

    assert command == [
        "multipass",
        "launch",
        "--name",
        "agent-vm",
        "--cpus",
        "1",
        "--memory",
        "1G",
        "--disk",
        "5G",
        "--timeout",
        "600",
    ]


def test_resolve_multipass_launch_timeout_seconds_returns_none_when_unset_or_empty(monkeypatch):
    monkeypatch.delenv(vm_module.MULTIPASS_LAUNCH_TIMEOUT_ENV_VAR, raising=False)
    assert vm_module.resolve_multipass_launch_timeout_seconds() is None

    monkeypatch.setenv(vm_module.MULTIPASS_LAUNCH_TIMEOUT_ENV_VAR, "   ")
    assert vm_module.resolve_multipass_launch_timeout_seconds() is None


def test_resolve_multipass_launch_timeout_seconds_parses_positive_int(monkeypatch):
    monkeypatch.setenv(vm_module.MULTIPASS_LAUNCH_TIMEOUT_ENV_VAR, "600")

    assert vm_module.resolve_multipass_launch_timeout_seconds() == 600


@pytest.mark.parametrize("value", ["0", "-5", "abc"])
def test_resolve_multipass_launch_timeout_seconds_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv(vm_module.MULTIPASS_LAUNCH_TIMEOUT_ENV_VAR, value)

    with pytest.raises(vm_module.MultipassError) as exc_info:
        vm_module.resolve_multipass_launch_timeout_seconds()

    assert vm_module.MULTIPASS_LAUNCH_TIMEOUT_ENV_VAR in str(exc_info.value)


def test_do_launch_uses_timeout_from_env(monkeypatch):
    monkeypatch.setenv(vm_module.MULTIPASS_LAUNCH_TIMEOUT_ENV_VAR, "600")
    monkeypatch.setattr(vm_module, "compare_vm", lambda *_args: "absent")
    monkeypatch.setattr(vm_module, "_dump_cloud_init", lambda _data: None)

    commands = []

    def _fake_launch_with_retries(command, max_attempts=3):
        del max_attempts
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(vm_module, "_launch_with_retries", _fake_launch_with_retries)

    result = vm_module.do_launch(_sample_vm(), "{}")

    assert result == "VM agent-vm created."
    assert commands == [
        [
            "multipass",
            "launch",
            "--name",
            "agent-vm",
            "--cpus",
            "1",
            "--memory",
            "1G",
            "--disk",
            "5G",
            "--timeout",
            "600",
        ]
    ]
