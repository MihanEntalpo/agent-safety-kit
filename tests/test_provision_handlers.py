from __future__ import annotations

from pathlib import Path

from agsekit_cli.provision_handlers import ProvisionHostAnsible, ProvisionWindowsVmControlNode, choose_provision_handler


def test_choose_provision_handler_uses_windows_handler(monkeypatch):
    monkeypatch.setattr("agsekit_cli.provision_handlers.is_windows", lambda: True)

    handler = choose_provision_handler()

    assert isinstance(handler, ProvisionWindowsVmControlNode)


def test_choose_provision_handler_uses_host_handler(monkeypatch):
    monkeypatch.setattr("agsekit_cli.provision_handlers.is_windows", lambda: False)

    handler = choose_provision_handler()

    assert isinstance(handler, ProvisionHostAnsible)


def test_windows_handler_reuses_ready_control_node(monkeypatch, tmp_path: Path):
    events = []
    handler = ProvisionWindowsVmControlNode()

    class DummyRunner:
        def ensure_ready(self, *, progress=None, debug=False):
            del progress, debug
            events.append("ensure-ready")

    dummy_runner = DummyRunner()
    monkeypatch.setattr(handler, "_runner", lambda vm_name: dummy_runner)
    monkeypatch.setattr("agsekit_cli.provision_handlers.ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        "agsekit_cli.provision_handlers.ensure_host_ssh_keypair",
        lambda ssh_dir, verbose=False: (tmp_path / "id_rsa", tmp_path / "id_rsa.pub"),
    )
    monkeypatch.setattr("agsekit_cli.provision_handlers._fetch_vm_ips", lambda *args, **kwargs: ["10.0.0.10"])
    monkeypatch.setattr("agsekit_cli.provision_handlers.bootstrap_vm_ssh_with_multipass", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        dummy_runner,
        "run_playbook",
        lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
        raising=False,
    )

    vm = type("Vm", (), {"name": "agent", "proxychains": None, "proxychains_defined": False})()
    playbook = tmp_path / "agent.yml"
    playbook.write_text("[]\n", encoding="utf-8")

    handler.install_agent(vm, playbook, tmp_path)
    handler.install_agent(vm, playbook, tmp_path, prepared_ssh=type("Prepared", (), {"private_key": tmp_path / "id_rsa", "vm_host": "10.0.0.10"})())

    assert events == ["ensure-ready"]
