from __future__ import annotations

import sys
from typing import Any, Dict

from pathlib import Path

import click
import pytest

import agsekit_cli.cli as cli_module
import agsekit_cli.interactive as interactive
import agsekit_cli.config as config_module
from agsekit_cli.config import AgentConfig, MountConfig


class DummyPrompt:
    def __init__(self, value: Any):
        self._value = value

    def ask(self) -> Any:
        return self._value


class DummyQuestionary:
    class Choice:
        def __init__(self, title: str, value: Any = None):
            self.title = title
            self.value = value

    @staticmethod
    def confirm(*_args: Any, **_kwargs: Any) -> DummyPrompt:
        return DummyPrompt(True)


def _register_cli_commands() -> None:
    for command in (
        cli_module.prepare_command,
        cli_module.up_command,
        cli_module.create_vm_command,
        cli_module.create_vms_command,
        cli_module.backup_once_command,
        cli_module.backup_clean_command,
        cli_module.backup_repeated_command,
        cli_module.backup_repeated_mount_command,
        cli_module.backup_repeated_all_command,
        cli_module.addmount_command,
        cli_module.removemount_command,
        cli_module.mount_command,
        cli_module.umount_command,
        cli_module.install_agents_command,
        cli_module.list_bundles_command,
        cli_module.restart_vm_command,
        cli_module.start_vm_command,
        cli_module.stop_vm_command,
        cli_module.run_command,
        cli_module.shell_command,
        cli_module.ssh_command,
        cli_module.portforward_command,
        cli_module.config_gen_command,
        cli_module.config_example_command,
        cli_module.pip_upgrade_command,
        cli_module.check_new_version_command,
        cli_module.version_command,
        cli_module.status_command,
        cli_module.doctor_command,
        cli_module.down_command,
        cli_module.daemon_group,
        cli_module.systemd_group,
        cli_module.destroy_vm_command,
    ):
        if command.name not in cli_module.cli.commands:
            cli_module.cli.add_command(command)


def _validate_cli_args(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    _register_cli_commands()

    def noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    def patch_callbacks(command: click.Command) -> None:
        monkeypatch.setattr(command, "callback", noop)
        if isinstance(command, click.Group):
            for subcommand in command.commands.values():
                patch_callbacks(subcommand)

    patch_callbacks(cli_module.cli)
    cli_module.cli.main(args=args, prog_name="agsekit", standalone_mode=False)


class InteractiveTestSession:
    def __init__(self, tmp_path: Path) -> None:
        self.config_path = tmp_path / "config.yaml"
        self.mount = MountConfig(
            source=tmp_path / "project",
            target=Path("/home/ubuntu/project"),
            backup=tmp_path / "backups",
            interval_minutes=5,
            vm_name="agent-vm",
        )
        self.agent = AgentConfig(name="qwen", type="qwen", version="0.15.11", env={}, vm_name=None)
        self.vms = {"agent-vm": object(), "agent-vm-2": object()}
        self._prompted_config_path = tmp_path / "custom-config.yaml"

    def load_mounts(self):
        return [self.mount]

    def load_vms(self):
        return self.vms

    def load_agents(self):
        return {"qwen": self.agent}

    def config_option(self):
        return ["--config", str(self.config_path)]

    def _prompt_config_path(self):
        self.config_path = self._prompted_config_path
        return self.config_path


@pytest.fixture(autouse=True)
def restore_sys_argv(monkeypatch):
    original = sys.argv[:]
    yield
    monkeypatch.setattr(sys, "argv", original)


def test_main_triggers_interactive_without_args(monkeypatch):
    called: Dict[str, Any] = {}

    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit"])

    def fake_run(cli, preselected_command=None, default_config_path=None):
        called["cli"] = cli
        called["preselected"] = preselected_command
        called["default_config_path"] = default_config_path

    monkeypatch.setattr(cli_module, "run_interactive", fake_run)

    cli_module.main()

    assert called["cli"] is cli_module.cli
    assert called["preselected"] is None


def test_main_falls_back_to_interactive_on_missing_params(monkeypatch):
    called: Dict[str, Any] = {}

    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit", "backup-once"])

    def fake_run(cli, preselected_command=None, default_config_path=None):
        called["cli"] = cli
        called["preselected"] = preselected_command
        called["default_config_path"] = default_config_path

    monkeypatch.setattr(cli_module, "run_interactive", fake_run)

    cli_module.main()

    assert called["cli"] is cli_module.cli
    assert called["preselected"] == "backup-once"
    assert called["default_config_path"] is None


def test_main_prompts_for_config_when_missing(monkeypatch, tmp_path):
    called: Dict[str, Any] = {}
    missing_config = tmp_path / "absent.yaml"

    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit", "run", "qwen"])
    monkeypatch.setattr(cli_module, "resolve_config_path", lambda _path=None: missing_config)

    def fake_run(cli, preselected_command=None, default_config_path=None):
        called["cli"] = cli
        called["preselected"] = preselected_command
        called["default_config_path"] = default_config_path

    monkeypatch.setattr(cli_module, "run_interactive", fake_run)

    cli_module.main()

    assert called["cli"] is cli_module.cli
    assert called["preselected"] == "run"
    assert called["default_config_path"] == missing_config


def test_run_interactive_executes_selected_command(monkeypatch):
    dummy_cli = click.Group()

    @dummy_cli.command(name="prepare")
    def prepare_command():
        pass

    monkeypatch.setattr(interactive, "_command_builders", lambda: {"prepare": lambda session: ["prepare"]})

    executed: Dict[str, Any] = {}

    def fake_main(*, args, prog_name):
        executed["args"] = args
        executed["prog_name"] = prog_name

    monkeypatch.setattr(dummy_cli, "main", fake_main)
    monkeypatch.setattr(interactive, "questionary", DummyQuestionary)

    interactive.run_interactive(dummy_cli, preselected_command="prepare")

    assert executed["args"] == ["prepare"]
    assert executed["prog_name"] == "agsekit"


def test_main_keeps_standard_help_when_not_interactive(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: False)
    monkeypatch.setattr(sys, "argv", ["agsekit", "--help"])

    cli_module.main()

    captured = capsys.readouterr()
    assert "Agent Safety Kit CLI" in captured.out


def test_main_skips_interactive_when_flag_is_set(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit", "--non-interactive"])

    def fail_if_called(*_args: Any, **_kwargs: Any) -> None:  # pragma: no cover - defensive
        raise AssertionError("interactive mode should not be invoked when --non-interactive is provided")

    monkeypatch.setattr(cli_module, "run_interactive", fail_if_called)

    cli_module.main()

    captured = capsys.readouterr()
    assert "Agent Safety Kit CLI" in captured.out


def test_main_reports_missing_params_without_interactive_when_flag_is_set(monkeypatch):
    called: Dict[str, Any] = {"interactive": False}

    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit", "create-vm", "--non-interactive"])

    def mark_called(*_args: Any, **_kwargs: Any) -> None:  # pragma: no cover - defensive
        called["interactive"] = True

    monkeypatch.setattr(cli_module, "run_interactive", mark_called)

    with pytest.raises(SystemExit) as excinfo:
        cli_module.main()

    assert excinfo.value.code == 1
    assert called["interactive"] is False


def test_main_reports_missing_config_without_interactive(monkeypatch, tmp_path):
    missing_config = tmp_path / "absent.yaml"
    called: Dict[str, Any] = {"interactive": False}

    monkeypatch.setattr(cli_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(sys, "argv", ["agsekit", "run", "qwen", "--non-interactive"])
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", missing_config)

    def mark_called(*_args: Any, **_kwargs: Any) -> None:  # pragma: no cover - defensive
        called["interactive"] = True

    monkeypatch.setattr(cli_module, "run_interactive", mark_called)

    with pytest.raises(SystemExit) as excinfo:
        cli_module.main()

    assert excinfo.value.code == 1
    assert called["interactive"] is False


def test_build_run_skips_vm_argument_when_auto_selected(monkeypatch, tmp_path):
    agent = AgentConfig(name="qwen", type="qwen", version="0.15.11", env={}, vm_name=None)
    mount = MountConfig(
        source=tmp_path,
        target=Path("/home/ubuntu/project"),
        backup=tmp_path / "backups",
        interval_minutes=5,
        vm_name="agents-ubuntu",
    )

    class DummySession:
        def load_agents(self):
            return {"qwen": agent}

        def load_mounts(self):
            return [mount]

        def load_vms(self):
            return {"agents-ubuntu": object()}

        def config_option(self):
            return ["--config", "config.yaml"]

    selections = [agent, mount, "__auto_vm__"]
    confirms = [False]
    texts = [""]

    class Prompt:
        def __init__(self, value):
            self.value = value

        def ask(self):
            return self.value

    class FakeQuestionary:
        @staticmethod
        def select(*_args, **_kwargs):
            return Prompt(selections.pop(0))

        @staticmethod
        def confirm(*_args, **_kwargs):
            return Prompt(confirms.pop(0))

        @staticmethod
        def text(*_args, **_kwargs):
            return Prompt(texts.pop(0))

    FakeQuestionary.Choice = interactive.questionary.Choice

    monkeypatch.setattr(interactive, "questionary", FakeQuestionary)

    args = interactive.build_run(DummySession())

    assert args == ["run", "--workdir", str(tmp_path), "--config", "config.yaml", "qwen"]


def test_build_daemon_entries(monkeypatch):
    prompts = ["custom-config.yaml"]

    class DummySession:
        def __init__(self):
            self.config_path = Path("default-config.yaml")

        def _prompt_config_path(self):
            self.config_path = Path(prompts.pop(0))
            return self.config_path

        def config_option(self):
            return ["--config", str(self.config_path)]

    session = DummySession()

    assert interactive.build_daemon_install(session) == ["daemon", "install", "--config", "custom-config.yaml"]
    assert interactive.build_daemon_uninstall(session) == ["daemon", "uninstall"]
    assert interactive.build_daemon_start(session) == ["daemon", "start"]
    assert interactive.build_daemon_stop(session) == ["daemon", "stop"]
    assert interactive.build_daemon_restart(session) == ["daemon", "restart"]
    assert interactive.build_daemon_status(session) == ["daemon", "status"]


def test_build_mount_uses_positional_source(monkeypatch, tmp_path):
    session = InteractiveTestSession(tmp_path)
    monkeypatch.setattr(interactive, "_select_from_list", lambda *_args, **_kwargs: session.mount)

    args = interactive.build_mount(session)

    assert args == ["mount", str(session.mount.source), "--config", str(session.config_path)]


def test_build_umount_uses_positional_source(monkeypatch, tmp_path):
    session = InteractiveTestSession(tmp_path)
    monkeypatch.setattr(interactive, "_select_from_list", lambda *_args, **_kwargs: session.mount)

    args = interactive.build_umount(session)

    assert args == ["umount", str(session.mount.source), "--config", str(session.config_path)]


@pytest.mark.parametrize(
    ("command_name", "expected_args"),
    [
        ("addmount", ["addmount"]),
        ("backup-clean", None),
        ("backup-once", None),
        ("backup-repeated", None),
        ("backup-repeated-all", None),
        ("backup-repeated-mount", None),
        ("check-new-version", None),
        ("config-example", ["config-example"]),
        ("config-gen", ["config-gen"]),
        ("create-vm", None),
        ("create-vms", None),
        ("daemon-install", None),
        ("daemon-restart", ["daemon", "restart"]),
        ("daemon-start", ["daemon", "start"]),
        ("daemon-status", ["daemon", "status"]),
        ("daemon-stop", ["daemon", "stop"]),
        ("daemon-uninstall", ["daemon", "uninstall"]),
        ("destroy-vm", None),
        ("down", None),
        ("install-agents", None),
        ("mount", None),
        ("pip-upgrade", ["pip-upgrade"]),
        ("portforward", None),
        ("prepare", ["prepare"]),
        ("removemount", ["removemount"]),
        ("restart-vm", None),
        ("run", None),
        ("shell", None),
        ("ssh", None),
        ("start-vm", None),
        ("status", None),
        ("stop-vm", None),
        ("umount", None),
        ("up", None),
    ],
)
def test_interactive_builders_generate_valid_cli_commands(monkeypatch, tmp_path, command_name, expected_args):
    session = InteractiveTestSession(tmp_path)
    builders = interactive._command_builders()

    select_answers = {
        "backup-clean": [session.mount, "thin"],
        "backup-repeated-mount": [session.mount],
        "create-vm": ["agent-vm"],
        "destroy-vm": ["agent-vm"],
        "install-agents": ["qwen", "__default__"],
        "mount": [session.mount],
        "restart-vm": ["agent-vm"],
        "run": [session.agent, session.mount, "__auto_vm__"],
        "shell": ["agent-vm"],
        "ssh": ["agent-vm"],
        "start-vm": ["agent-vm"],
        "stop-vm": ["agent-vm"],
        "umount": [session.mount],
    }
    directory_answers = {
        "backup-once": [tmp_path / "src", tmp_path / "dst"],
        "backup-repeated": [tmp_path / "src", tmp_path / "dst"],
    }
    confirm_answers = {
        "backup-once": [False],
        "backup-repeated": [False],
        "run": [False],
    }
    text_answers = {
        "backup-clean": ["50"],
        "backup-repeated": ["5"],
        "run": [""],
        "ssh": [""],
    }

    select_queue = list(select_answers.get(command_name, []))
    directory_queue = list(directory_answers.get(command_name, []))
    confirm_queue = list(confirm_answers.get(command_name, []))
    text_queue = list(text_answers.get(command_name, []))

    monkeypatch.setattr(
        interactive,
        "_select_from_list",
        lambda *_args, **_kwargs: select_queue.pop(0),
    )
    monkeypatch.setattr(
        interactive,
        "_select_directory",
        lambda *_args, **_kwargs: directory_queue.pop(0),
    )

    class FakeQuestionary:
        Choice = interactive.questionary.Choice
        Separator = interactive.questionary.Separator

        @staticmethod
        def confirm(*_args: Any, **_kwargs: Any) -> DummyPrompt:
            return DummyPrompt(confirm_queue.pop(0))

        @staticmethod
        def text(*_args: Any, **_kwargs: Any) -> DummyPrompt:
            return DummyPrompt(text_queue.pop(0))

    monkeypatch.setattr(interactive, "questionary", FakeQuestionary)

    args = builders[command_name](session)

    if expected_args is not None:
        assert args == expected_args or args == [*expected_args, "--config", str(session.config_path)]
    _validate_cli_args(monkeypatch, args)
    assert not select_queue
    assert not directory_queue
    assert not confirm_queue
    assert not text_queue


def test_select_command_places_up_before_prepare_and_lists_daemon_actions(monkeypatch):
    dummy_cli = click.Group()

    @dummy_cli.command(name="prepare", help="prepare help")
    def prepare_command():
        pass

    @dummy_cli.command(name="up", help="up help")
    def up_command():
        pass

    @dummy_cli.command(name="config-example", help="config-example help")
    def config_example_command():
        pass

    @dummy_cli.command(name="config-gen", help="config-gen help")
    def config_gen_command():
        pass

    @dummy_cli.command(name="pip-upgrade", help="pip-upgrade help")
    def pip_upgrade_command():
        pass

    @dummy_cli.command(name="status", help="status help")
    def status_command():
        pass

    captured: Dict[str, Any] = {}

    class Prompt:
        def ask(self):
            return "up"

    class FakeQuestionary:
        Choice = interactive.questionary.Choice
        Separator = interactive.questionary.Separator

        @staticmethod
        def select(_message, *, choices, use_shortcuts=True):
            del use_shortcuts
            captured["titles"] = [choice.title for choice in choices if hasattr(choice, "title")]
            return Prompt()

    monkeypatch.setattr(interactive, "questionary", FakeQuestionary)

    builders = interactive._command_builders()
    selected = interactive._select_command(dummy_cli, builders, None)

    assert selected == "up"
    titles = captured["titles"]
    up_index = next(index for index, title in enumerate(titles) if title.strip().startswith("up "))
    prepare_index = next(index for index, title in enumerate(titles) if title.strip().startswith("prepare "))
    assert up_index < prepare_index
    assert any("daemon install" in title for title in titles)
    assert any("daemon uninstall" in title for title in titles)
    assert any("daemon start" in title for title in titles)
    assert any("daemon stop" in title for title in titles)
    assert any("daemon restart" in title for title in titles)
    assert any("daemon status" in title for title in titles)
