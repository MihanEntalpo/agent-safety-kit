import sys
from pathlib import Path

from typing import cast

import click
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.create_vm as create_vm_module
from agsekit_cli.commands.create_vm import create_vm_command


def _invoke_command(runner: CliRunner, command: click.Command, args: list[str]):
    return runner.invoke(cast(click.Command, command), args)


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
        lambda *_, **__: (Path("id_rsa"), Path("id_rsa.pub")),
    )
    monkeypatch.setattr(
        create_vm_module,
        "prepare_vm",
        lambda vm_name, public_key, *args, **kwargs: prep_calls.append((vm_name, public_key.name)),
    )

    runner = CliRunner()
    result = _invoke_command(runner, create_vm_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [(str(config_path), "agent")]
    assert prep_calls == [("agent", "id_rsa.pub")]
    assert "agent" in result.output


def test_create_vm_requires_name_when_multiple(tmp_path, monkeypatch):
    monkeypatch.setenv("AGSEKIT_LANG", "ru")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["first", "second"])

    runner = CliRunner()
    result = _invoke_command(runner, create_vm_command, ["--config", str(config_path)])

    assert result.exit_code != 0
    assert "Укажите имя ВМ" in result.output


def test_create_vm_wraps_prepare_errors(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    monkeypatch.setattr(create_vm_module, "create_vm_from_config", lambda path, vm_name: f"created {vm_name}")
    monkeypatch.setattr(
        create_vm_module,
        "ensure_host_ssh_keypair",
        lambda *_, **__: (Path("id_rsa"), Path("id_rsa.pub")),
    )

    def fail_prepare(*_args, **_kwargs):
        raise create_vm_module.MultipassError("prepare failed")

    monkeypatch.setattr(create_vm_module, "prepare_vm", fail_prepare)

    runner = CliRunner()
    result = _invoke_command(runner, create_vm_command, ["--config", str(config_path)])

    assert result.exit_code != 0
    assert "prepare failed" in result.output


def test_create_vm_debug_uses_dummy_progress_manager(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, ["agent"])

    progress_debug_args: list[bool] = []
    prepare_kwargs: list[dict[str, object]] = []

    monkeypatch.setattr(create_vm_module, "create_vm_from_config", lambda path, vm_name: f"created {vm_name}")
    monkeypatch.setattr(
        create_vm_module,
        "ensure_host_ssh_keypair",
        lambda *_, **__: (Path("id_rsa"), Path("id_rsa.pub")),
    )

    class DummyProgressManager:
        def __init__(self, *, debug: bool = False):
            progress_debug_args.append(debug)
            self.debug = debug

        def __bool__(self):
            return not self.debug

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def add_task(self, description, total):
            del description, total
            return 0

        def update(self, task_id, *, description=None, completed=None):
            del task_id, description, completed

        def advance(self, task_id, amount=1):
            del task_id, amount

    def fake_prepare_vm(vm_name, public_key, *args, **kwargs):
        del vm_name, public_key, args
        prepare_kwargs.append(kwargs)

    monkeypatch.setattr(create_vm_module, "ProgressManager", DummyProgressManager)
    monkeypatch.setattr(create_vm_module, "prepare_vm", fake_prepare_vm)

    runner = CliRunner()
    result = _invoke_command(runner, create_vm_command, ["--config", str(config_path), "--debug"])

    assert result.exit_code == 0
    assert progress_debug_args == [True]
    assert len(prepare_kwargs) == 1
    assert prepare_kwargs[0]["debug"] is True
    assert isinstance(prepare_kwargs[0]["progress"], DummyProgressManager)
    assert prepare_kwargs[0]["step_task_id"] == 0
