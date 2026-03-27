import sys
from pathlib import Path
from typing import cast

import click
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.up as up_module
import agsekit_cli.config as config_module
from agsekit_cli.commands.up import up_command


def _invoke_command(runner: CliRunner, command: click.Command, args: list[str]):
    return runner.invoke(cast(click.Command, command), args)


def test_up_runs_all_stages_by_default(monkeypatch, tmp_path):
    calls: list[tuple[str, object]] = []
    config_path = tmp_path / "config.yaml"
    config_path.write_text("vms: {}\n", encoding="utf-8")

    monkeypatch.setattr(up_module, "run_prepare", lambda **kwargs: calls.append(("prepare", kwargs.get("debug"))))
    monkeypatch.setattr(up_module, "run_create_vms", lambda *args, **kwargs: calls.append(("create-vms", args[0] if args else kwargs.get("config_path"))))
    monkeypatch.setattr(
        up_module,
        "run_install_agents",
        lambda **kwargs: calls.append(("install-agents", kwargs.get("all_agents"), kwargs.get("interactive"))),
    )
    monkeypatch.setattr(
        up_module,
        "install_portforward_service",
        lambda config_path, announce=False: calls.append(("systemd", Path(config_path), announce)),
    )

    runner = CliRunner()
    result = _invoke_command(runner, up_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [
        ("prepare", False),
        ("create-vms", str(config_path)),
        ("install-agents", True, False),
        ("systemd", config_path, False),
    ]
    assert "Setup completed successfully" in result.output


def test_up_respects_disabled_stages(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("vms: {}\n", encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr(up_module, "run_prepare", lambda **kwargs: calls.append("prepare"))
    monkeypatch.setattr(up_module, "run_create_vms", lambda *args, **kwargs: calls.append("create-vms"))
    monkeypatch.setattr(up_module, "run_install_agents", lambda **kwargs: calls.append("install-agents"))
    monkeypatch.setattr(up_module, "install_portforward_service", lambda *args, **kwargs: calls.append("systemd"))

    runner = CliRunner()
    result = _invoke_command(
        runner,
        up_command,
        ["--config", str(config_path), "--no-prepare", "--install-agents", "--no-create-vms"],
    )

    assert result.exit_code == 0
    assert calls == ["install-agents", "systemd"]


def test_up_requires_at_least_one_stage():
    runner = CliRunner()
    result = _invoke_command(
        runner,
        up_command,
        ["--no-prepare", "--no-create-vms", "--no-install-agents"],
    )

    assert result.exit_code != 0
    assert "Nothing to do" in result.output


def test_up_prepare_only_does_not_require_config_or_install_systemd(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(up_module, "run_prepare", lambda **kwargs: calls.append("prepare"))
    monkeypatch.setattr(up_module, "install_portforward_service", lambda *args, **kwargs: calls.append("systemd"))

    runner = CliRunner()
    result = _invoke_command(runner, up_command, ["--create-vms", "--no-create-vms", "--install-agents", "--no-install-agents"])

    assert result.exit_code == 0
    assert calls == ["prepare"]


def test_up_reports_helpful_error_when_default_config_missing(monkeypatch, tmp_path):
    missing_default = tmp_path / "missing-config.yaml"
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", missing_default)
    monkeypatch.setattr(up_module, "DEFAULT_CONFIG_PATH", missing_default)

    runner = CliRunner()
    result = _invoke_command(runner, up_command, [])

    assert result.exit_code != 0
    assert "config-gen" in result.output
    assert "config-example" in result.output
    assert str(missing_default) in result.output


def test_up_keeps_standard_error_for_explicit_missing_config(tmp_path):
    missing_config = tmp_path / "missing.yaml"

    runner = CliRunner()
    result = _invoke_command(runner, up_command, ["--config", str(missing_config)])

    assert result.exit_code != 0
    assert f"Config file not found: {missing_config}" in result.output


def test_up_passes_debug_and_shared_progress(monkeypatch, tmp_path):
    progress_debug_args: list[bool] = []
    prepare_calls: list[dict[str, object]] = []
    create_calls: list[dict[str, object]] = []
    install_calls: list[dict[str, object]] = []
    systemd_calls: list[dict[str, object]] = []
    config_path = tmp_path / "cfg.yml"
    config_path.write_text("vms: {}\n", encoding="utf-8")

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

        def update(self, task_id, *, description=None, completed=None, total=None):
            del task_id, description, completed, total

        def advance(self, task_id, amount=1):
            del task_id, amount

        def remove_task(self, task_id):
            del task_id

    monkeypatch.setattr(up_module, "ProgressManager", DummyProgressManager)
    monkeypatch.setattr(up_module, "run_prepare", lambda **kwargs: prepare_calls.append(kwargs))
    monkeypatch.setattr(up_module, "run_create_vms", lambda *args, **kwargs: create_calls.append({"config_path": args[0], **kwargs}))
    monkeypatch.setattr(up_module, "run_install_agents", lambda **kwargs: install_calls.append(kwargs))
    monkeypatch.setattr(
        up_module,
        "install_portforward_service",
        lambda config_path, announce=False: systemd_calls.append({"config_path": config_path, "announce": announce}),
    )

    runner = CliRunner()
    result = _invoke_command(runner, up_command, ["--config", str(config_path), "--debug"])

    assert result.exit_code == 0
    assert progress_debug_args == [True]
    assert prepare_calls and prepare_calls[0]["debug"] is True
    assert isinstance(prepare_calls[0]["progress"], DummyProgressManager)
    assert create_calls and create_calls[0]["config_path"] == str(config_path)
    assert create_calls[0]["debug"] is True
    assert create_calls[0]["progress"] is not None
    assert hasattr(create_calls[0]["progress"], "add_task")
    assert install_calls and install_calls[0]["all_agents"] is True
    assert install_calls[0]["interactive"] is False
    assert install_calls[0]["debug"] is True
    assert install_calls[0]["progress"] is not None
    assert hasattr(install_calls[0]["progress"], "add_task")
    assert systemd_calls == [{"config_path": config_path, "announce": True}]
