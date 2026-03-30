from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from agsekit_cli.commands import portforward as portforward_module
from agsekit_cli.config import PortForwardingRule, VmConfig


def test_find_privileged_remote_ports():
    rules = [
        PortForwardingRule(type="local", host_addr="127.0.0.1:8080", vm_addr="127.0.0.1:80"),
        PortForwardingRule(type="remote", host_addr="127.0.0.1:8080", vm_addr="127.0.0.1:80"),
        PortForwardingRule(type="remote", host_addr="127.0.0.1:8081", vm_addr="127.0.0.1:443"),
        PortForwardingRule(type="remote", host_addr="127.0.0.1:8082", vm_addr="127.0.0.1:8082"),
    ]

    ports = portforward_module._find_privileged_remote_ports(rules)

    assert ports == [80, 443]


def test_collect_forward_targets_ignores_vms_without_rules():
    vms = {
        "vm-with-rules": VmConfig(
            name="vm-with-rules",
            cpu=2,
            ram="4G",
            disk="20G",
            cloud_init={},
            port_forwarding=[
                PortForwardingRule(type="local", host_addr="127.0.0.1:8080", vm_addr="127.0.0.1:80"),
                PortForwardingRule(type="remote", host_addr="127.0.0.1:8081", vm_addr="127.0.0.1:81"),
            ],
        ),
        "vm-without-rules": VmConfig(
            name="vm-without-rules",
            cpu=2,
            ram="4G",
            disk="20G",
            cloud_init={},
            port_forwarding=[],
        ),
    }

    targets = portforward_module._collect_forward_targets(vms)

    assert list(targets) == ["vm-with-rules"]
    assert targets["vm-with-rules"] == portforward_module.ForwarderTarget(
        port_args=("-L", "127.0.0.1:8080:127.0.0.1:80", "-R", "127.0.0.1:81:127.0.0.1:8081"),
        privileged_remote_ports=(81,),
    )


@dataclass
class FakeProc:
    return_code: Optional[int] = None
    terminated: bool = False
    killed: bool = False
    waited: bool = False

    def poll(self):
        return self.return_code

    def terminate(self):
        self.terminated = True
        self.return_code = 0

    def wait(self, timeout=None):
        del timeout
        self.waited = True
        return self.return_code

    def kill(self):
        self.killed = True
        self.return_code = -9


def test_reconcile_forwarders_handles_vm_add_remove_and_port_change(monkeypatch):
    current_targets = {
        "removed-vm": portforward_module.ForwarderTarget(port_args=("-L", "1"), privileged_remote_ports=()),
        "changed-vm": portforward_module.ForwarderTarget(port_args=("-L", "2"), privileged_remote_ports=()),
    }
    desired_targets = {
        "changed-vm": portforward_module.ForwarderTarget(port_args=("-L", "3"), privileged_remote_ports=(443,)),
        "new-vm": portforward_module.ForwarderTarget(port_args=("-D", "1080"), privileged_remote_ports=()),
    }
    removed_proc = FakeProc()
    changed_proc = FakeProc()
    processes = {
        "removed-vm": removed_proc,
        "changed-vm": changed_proc,
    }
    started: list[tuple[str, tuple[str, ...], bool]] = []

    monkeypatch.setattr(
        portforward_module,
        "_start_forwarder",
        lambda base_command, vm_name, config_path, port_args, debug=False: (
            started.append((vm_name, tuple(port_args), debug)) or FakeProc()
        ),
    )

    portforward_module._reconcile_forwarders(
        processes,
        current_targets,
        desired_targets,
        ["agsekit"],
        Path("/tmp/config.yaml"),
        debug=True,
    )

    assert removed_proc.terminated is True
    assert changed_proc.terminated is True
    assert sorted(started) == [
        ("changed-vm", ("-L", "3"), True),
        ("new-vm", ("-D", "1080"), True),
    ]
    assert set(processes) == {"changed-vm", "new-vm"}


def test_reconcile_forwarders_handles_vm_gaining_first_port_and_losing_last_port(monkeypatch):
    current_targets = {
        "vm-loses-last-port": portforward_module.ForwarderTarget(port_args=("-L", "1"), privileged_remote_ports=()),
    }
    desired_targets = {
        "vm-gains-first-port": portforward_module.ForwarderTarget(port_args=("-R", "2"), privileged_remote_ports=()),
    }
    removed_proc = FakeProc()
    processes = {"vm-loses-last-port": removed_proc}
    started: list[str] = []

    monkeypatch.setattr(
        portforward_module,
        "_start_forwarder",
        lambda base_command, vm_name, config_path, port_args, debug=False: (started.append(vm_name) or FakeProc()),
    )

    portforward_module._reconcile_forwarders(
        processes,
        current_targets,
        desired_targets,
        ["agsekit"],
        Path("/tmp/config.yaml"),
    )

    assert removed_proc.terminated is True
    assert started == ["vm-gains-first-port"]
    assert set(processes) == {"vm-gains-first-port"}


def test_load_portforward_runtime_reads_check_interval(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        (
            "global:\n"
            "  portforward_config_check_interval_sec: 17\n"
            "vms:\n"
            "  agent:\n"
            "    cpu: 1\n"
            "    ram: 1G\n"
            "    disk: 5G\n"
            "    port-forwarding:\n"
            "      - type: local\n"
            "        host-addr: 127.0.0.1:8080\n"
            "        vm-addr: 127.0.0.1:80\n"
        ),
        encoding="utf-8",
    )

    runtime = portforward_module._load_portforward_runtime(config_path)

    assert runtime.check_interval_sec == 17
    assert runtime.targets == {
        "agent": portforward_module.ForwarderTarget(
            port_args=("-L", "127.0.0.1:8080:127.0.0.1:80"),
            privileged_remote_ports=(),
        )
    }


def test_maybe_reload_forward_targets_warns_and_keeps_state_on_config_error(monkeypatch):
    current_targets = {
        "vm1": portforward_module.ForwarderTarget(port_args=("-L", "1"), privileged_remote_ports=()),
    }
    processes = {"vm1": FakeProc()}
    messages: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        portforward_module,
        "_load_portforward_runtime",
        lambda config_path: (_ for _ in ()).throw(portforward_module.ConfigError("broken config")),
    )
    monkeypatch.setattr(
        portforward_module.click,
        "echo",
        lambda message, err=False: messages.append((str(message), err)),
    )

    result_targets, result_interval, warning = portforward_module._maybe_reload_forward_targets(
        Path("/tmp/config.yaml"),
        current_targets,
        10,
        processes,
        ["agsekit"],
    )

    assert result_targets == current_targets
    assert result_interval == 10
    assert warning is not None
    assert messages == [("Warning: failed to reload port-forwarding configuration from /tmp/config.yaml: broken config", True)]


def test_maybe_reload_forward_targets_applies_config_changes_and_clears_previous_warning(monkeypatch):
    current_targets = {
        "vm1": portforward_module.ForwarderTarget(port_args=("-L", "1"), privileged_remote_ports=()),
    }
    desired_targets = {
        "vm2": portforward_module.ForwarderTarget(port_args=("-D", "2"), privileged_remote_ports=()),
    }
    processes = {"vm1": FakeProc()}
    messages: list[tuple[str, bool]] = []
    reconcile_calls: list[tuple[dict[str, portforward_module.ForwarderTarget], dict[str, portforward_module.ForwarderTarget]]] = []

    monkeypatch.setattr(
        portforward_module,
        "_load_portforward_runtime",
        lambda config_path: portforward_module.PortforwardRuntimeConfig(
            targets=desired_targets,
            check_interval_sec=15,
        ),
    )
    monkeypatch.setattr(
        portforward_module,
        "_reconcile_forwarders",
        lambda processes, current, desired, base_command, config_path, debug=False: reconcile_calls.append((current, desired)),
    )
    monkeypatch.setattr(
        portforward_module.click,
        "echo",
        lambda message, err=False: messages.append((str(message), err)),
    )

    result_targets, result_interval, warning = portforward_module._maybe_reload_forward_targets(
        Path("/tmp/config.yaml"),
        current_targets,
        10,
        processes,
        ["agsekit"],
        last_warning="old warning",
    )

    assert result_targets == desired_targets
    assert result_interval == 15
    assert warning is None
    assert reconcile_calls == [(current_targets, desired_targets)]
    assert messages == [
        ("Port-forwarding configuration reload recovered: /tmp/config.yaml", False),
        ("Port-forwarding configuration changed in /tmp/config.yaml. Reconnecting affected tunnels...", False),
    ]
