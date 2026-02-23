from __future__ import annotations

import json

import agsekit_cli.vm as vm_module


def test_compare_vm_uses_runtime_info_when_list_lacks_resources(monkeypatch):
    raw_info = json.dumps(
        {
            "list": [
                {
                    "name": "agent-vm",
                    "state": "Running",
                }
            ]
        }
    )

    runtime_info = {
        "cpu_count": "1",
        "memory": {"total": 1024 ** 3},
        "disks": {"sda1": {"total": str(5 * (1024 ** 3))}},
    }

    monkeypatch.setattr(vm_module, "_fetch_runtime_info_entry", lambda _name: runtime_info)

    result = vm_module.compare_vm(raw_info, "agent-vm", "1", "1G", "5G")

    assert result == "match"


def test_compare_vm_detects_cpu_mismatch_from_runtime_info(monkeypatch):
    raw_info = json.dumps(
        {
            "list": [
                {
                    "name": "agent-vm",
                    "state": "Running",
                }
            ]
        }
    )

    runtime_info = {
        "cpu_count": "2",
        "memory": {"total": 1024 ** 3},
        "disks": {"sda1": {"total": str(5 * (1024 ** 3))}},
    }

    monkeypatch.setattr(vm_module, "_fetch_runtime_info_entry", lambda _name: runtime_info)

    result = vm_module.compare_vm(raw_info, "agent-vm", "1", "1G", "5G")

    assert result == "mismatch cpus"


def test_compare_vm_absent_does_not_query_runtime_info(monkeypatch):
    raw_info = json.dumps({"list": []})
    called = {"value": False}

    def _fake_fetch(_name: str):
        called["value"] = True
        return {}

    monkeypatch.setattr(vm_module, "_fetch_runtime_info_entry", _fake_fetch)

    result = vm_module.compare_vm(raw_info, "missing-vm", "1", "1G", "5G")

    assert result == "absent"
    assert called["value"] is False


def test_compare_vm_tolerates_small_memory_and_disk_deviation(monkeypatch):
    raw_info = json.dumps(
        {
            "list": [
                {
                    "name": "agent-vm",
                    "state": "Running",
                }
            ]
        }
    )

    runtime_info = {
        "cpu_count": "1",
        "memory": {"total": 1002348544},
        "disks": {"sda1": {"total": 5116440064}},
    }

    monkeypatch.setattr(vm_module, "_fetch_runtime_info_entry", lambda _name: runtime_info)

    result = vm_module.compare_vm(raw_info, "agent-vm", "1", "1G", "5G")

    assert result == "match"


def test_compare_vm_reports_large_memory_and_disk_deviation(monkeypatch):
    raw_info = json.dumps(
        {
            "list": [
                {
                    "name": "agent-vm",
                    "state": "Running",
                }
            ]
        }
    )

    runtime_info = {
        "cpu_count": "1",
        "memory": {"total": 700 * (1024 ** 2)},
        "disks": {"sda1": {"total": 3 * (1024 ** 3)}},
    }

    monkeypatch.setattr(vm_module, "_fetch_runtime_info_entry", lambda _name: runtime_info)

    result = vm_module.compare_vm(raw_info, "agent-vm", "1", "1G", "5G")

    assert result == "mismatch memory;disk"
