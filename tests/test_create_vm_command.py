import sys
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.create_vm as create_vm_module
from agsekit_cli.commands.create_vm import create_vm_command


def _write_config(config_path: Path, vm_names: list[str]) -> None:
    entries = "\n".join(f"  {name}:\n    cpu: 1\n    ram: 1G\n    disk: 5G" for name in vm_names)
    config_path.write_text(f"vms:\n{entries}\n", encoding="utf-8")


def test_create_vm_defaults_to_single_vm(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    calls: list[tuple[str, str]] = []
    prep_calls: list[tuple[str, str]] = []

    def fake_create_vm_from_config(path: str, vm_name: str) -> str:
        calls.append((path, vm_name))
        return f"created {vm_name}"

    monkeypatch.setattr(create_vm_module, "create_vm_from_config", fake_create_vm_from_config)
    monkeypatch.setattr(
        create_vm_module,
        "ensure_host_ssh_keypair",
        lambda: (Path("id_rsa"), Path("id_rsa.pub")),
    )
    monkeypatch.setattr(
        create_vm_module,
        "prepare_vm",
        lambda vm_name, public_key: prep_calls.append((vm_name, public_key.name)),
    )

    runner = CliRunner()
    result = runner.invoke(create_vm_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [(str(config_path), "agent")]
    assert prep_calls == [("agent", "id_rsa.pub")]
    assert "agent" in result.output


def test_create_vm_requires_name_when_multiple(tmp_path, monkeypatch):
    monkeypatch.setenv("AGSEKIT_LANG", "ru")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["first", "second"])

    runner = CliRunner()
    result = runner.invoke(create_vm_command, ["--config", str(config_path)])

    assert result.exit_code != 0
    assert "Укажите имя ВМ" in result.output
