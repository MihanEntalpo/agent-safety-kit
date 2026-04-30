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


def test_system_memory_bytes_uses_psutil_when_sysconf_is_unavailable(monkeypatch):
    class Memory:
        total = 16 * 1024 ** 3

    def fake_sysconf(_name):
        raise AttributeError("sysconf is unavailable")

    monkeypatch.setattr(vm_module.os, "sysconf", fake_sysconf)
    monkeypatch.setattr(vm_module.psutil, "virtual_memory", lambda: Memory())

    assert vm_module._system_memory_bytes() == 16 * 1024 ** 3


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


def test_do_launch_wraps_known_hyperv_components_error(monkeypatch):
    monkeypatch.setattr(vm_module, "compare_vm", lambda *_args: "absent")
    monkeypatch.setattr(vm_module, "_dump_cloud_init", lambda _data: None)

    stderr = "\n".join(
        [
            'Start-VM : "agent-vm": Не удалось запустить виртуальную машину.',
            'Не удалось запустить виртуальную машину "agent-vm", потому что не запущен один из компонентов Hyper-V.',
            'FullyQualifiedErrorId : OperationFailed,Microsoft.HyperV.PowerShell.Commands.StartVM',
        ]
    )

    monkeypatch.setattr(
        vm_module,
        "_launch_with_retries",
        lambda _command: subprocess.CompletedProcess(["multipass", "launch"], 1, stdout="", stderr=stderr),
    )

    with pytest.raises(vm_module.MultipassError) as exc_info:
        vm_module.do_launch(_sample_vm(), "{}")

    message = str(exc_info.value)
    assert "nested virtualization" in message
    assert "Hyper-V" in message
    assert "Start-VM" not in message


def test_do_launch_wraps_unknown_hyperv_start_error_generically(monkeypatch):
    monkeypatch.setattr(vm_module, "compare_vm", lambda *_args: "absent")
    monkeypatch.setattr(vm_module, "_dump_cloud_init", lambda _data: None)

    stderr = "\n".join(
        [
            'Start-VM : "agent-vm": Unexpected failure.',
            "VirtualizationException",
            "FullyQualifiedErrorId : OperationFailed,Microsoft.HyperV.PowerShell.Commands.StartVM",
        ]
    )

    monkeypatch.setattr(
        vm_module,
        "_launch_with_retries",
        lambda _command: subprocess.CompletedProcess(["multipass", "launch"], 1, stdout="", stderr=stderr),
    )

    with pytest.raises(vm_module.MultipassError) as exc_info:
        vm_module.do_launch(_sample_vm(), "{}")

    message = str(exc_info.value)
    assert "Hyper-V startup problem" in message
    assert "Unexpected failure." not in message


def test_wrap_multipass_hyperv_error_uses_windows_vmms_event_ids_for_garbled_output(monkeypatch):
    monkeypatch.setattr(vm_module, "is_windows", lambda: True)
    monkeypatch.setattr(vm_module, "_lookup_recent_hyperv_vmms_event_ids", lambda _vm_name: ["15130", "20144"])

    stderr = "\n".join(
        [
            'launch failed: Start-VM : "agent-vm": ?? ??????? ?????????.',
            '?? ??????? ????????? ??????????? ?????? "agent-vm", ??? ??? ?? ???????? ???? ?? ??????????? Hyper-V.',
            "FullyQualifiedErrorId : OperationFailed,Microsoft.HyperV.PowerShell.Commands.StartVM",
        ]
    )

    message = vm_module.wrap_multipass_hyperv_error(stderr)

    assert message is not None
    assert "nested virtualization" in message
    assert "Start-VM" not in message
