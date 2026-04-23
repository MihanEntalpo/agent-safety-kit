import json
import sys
from pathlib import Path
from typing import Dict, Optional

from typing import cast

import click
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.install_agents as install_agents_module
from agsekit_cli.ansible_utils import AnsiblePlaybookResult
from agsekit_cli.commands.install_agents import install_agents_command
from agsekit_cli.i18n import tr


def _write_config(
    config_path: Path,
    agents: list[tuple[str, str]],
    *,
    vm_names: Optional[list[str]] = None,
    vm_proxychains: Optional[str] = None,
    agent_proxychains: Optional[Dict[str, str]] = None,
    agent_vm: Optional[Dict[str, str]] = None,
    agent_vms: Optional[Dict[str, object]] = None,
) -> None:
    defined_vm_names = vm_names if vm_names else ["agent"]
    vm_entries: list[str] = []
    for name in defined_vm_names:
        vm_proxychains_line = f"    proxychains: {json.dumps(vm_proxychains)}\n" if vm_proxychains is not None else ""
        vm_entries.append(f"  {name}:\n    cpu: 1\n    ram: 1G\n    disk: 5G\n{vm_proxychains_line}")
    joined_vm_entries = "".join(vm_entries)

    proxychains_by_agent = agent_proxychains or {}
    vm_by_agent = agent_vm or {}
    vms_by_agent = agent_vms or {}
    agent_entries = []
    for name, agent_type in agents:
        proxychains_line = ""
        if name in proxychains_by_agent:
            proxychains_line = f"    proxychains: {json.dumps(proxychains_by_agent[name])}\n"
        vm_line = f"    vm: {json.dumps(vm_by_agent[name])}\n" if name in vm_by_agent else ""
        vms_line = f"    vms: {json.dumps(vms_by_agent[name])}\n" if name in vms_by_agent else ""
        agent_entries.append(
            f"  {name}:\n    type: {agent_type}\n{vm_line}{vms_line}{proxychains_line}    env:\n      TOKEN: abc"
        )
    joined_agent_entries = "\n".join(agent_entries)

    config_path.write_text(
        f"""
vms:
{joined_vm_entries}agents:
{joined_agent_entries}
""",
        encoding="utf-8",
    )


def _invoke_command(runner: CliRunner, command: click.Command, args: list[str]):
    return runner.invoke(cast(click.Command, command), args)


def test_install_agents_defaults_to_single_agent(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("qwen", "qwen")])

    calls: list[tuple[str, str]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **_kwargs) -> None:
        calls.append((vm.name, playbook_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls and calls[0][0] == "agent"
    assert calls[0][1] == "qwen.yml"
    assert calls[0][2] is None


def test_install_agents_passes_configured_ssh_keys_folder(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    ssh_dir = tmp_path / "custom-ssh"
    _write_config(config_path, [("qwen", "qwen")])
    config_path.write_text(
        "global:\n"
        f"  ssh_keys_folder: {ssh_dir}\n"
        + config_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    calls: list[Path] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **kwargs) -> None:
        del vm, playbook_path, proxychains
        calls.append(kwargs["ssh_keys_folder"])

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [ssh_dir.resolve()]


def test_run_install_playbook_bootstraps_keys_then_uses_ssh(monkeypatch, tmp_path):
    ssh_dir = tmp_path / "custom-ssh"
    private_key = ssh_dir / "id_rsa"
    public_key = ssh_dir / "id_rsa.pub"
    playbook_path = tmp_path / "qwen.yml"
    playbook_path.write_text("- hosts: all\n  tasks: []\n", encoding="utf-8")
    vm = install_agents_module.VmConfig(
        name="agent",
        cpu=1,
        ram="1G",
        disk="5G",
        cloud_init={},
        port_forwarding=[],
    )
    events: list[object] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(install_agents_module, "ensure_multipass_available", lambda: events.append("ensure-multipass"))
    monkeypatch.setattr(
        install_agents_module,
        "ensure_host_ssh_keypair",
        lambda ssh_dir, verbose=False: events.append(("keys", ssh_dir, verbose)) or (private_key, public_key),
    )
    monkeypatch.setattr(
        install_agents_module,
        "_fetch_vm_ips",
        lambda vm_name, **_kwargs: events.append(("ips", vm_name)) or ["10.0.0.15"],
    )
    monkeypatch.setattr(
        install_agents_module,
        "_ensure_vm_ssh_access",
        lambda vm_name, public_key, hosts, **_kwargs: events.append(("bootstrap", vm_name, public_key, hosts)),
    )

    def fake_run_ansible_playbook(command, *, playbook_path, **_kwargs):
        events.append(("ansible", list(command), Path(playbook_path)))
        return Result()

    monkeypatch.setattr(install_agents_module, "run_ansible_playbook", fake_run_ansible_playbook)

    install_agents_module._run_install_playbook(vm, playbook_path, ssh_keys_folder=ssh_dir, debug=True)

    assert events[:4] == [
        "ensure-multipass",
        ("keys", ssh_dir, True),
        ("ips", "agent"),
        ("bootstrap", "agent", public_key, ["agent", "10.0.0.15"]),
    ]
    ansible_event = events[4]
    assert isinstance(ansible_event, tuple)
    command = ansible_event[1]
    payload = json.loads(command[command.index("-e") + 1])
    assert payload["ansible_connection"] == "ssh"
    assert payload["ansible_host"] == "10.0.0.15"
    assert payload["ansible_ssh_private_key_file"] == str(private_key.resolve())


def test_install_agents_uses_cline_playbook(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("cline_main", "cline")])

    calls: list[tuple[str, str]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **_kwargs) -> None:
        del proxychains
        calls.append((vm.name, playbook_path.name))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [("agent", "cline.yml")]


def test_install_agents_uses_opencode_playbook(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("opencode_main", "opencode")])

    calls: list[tuple[str, str]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **_kwargs) -> None:
        del proxychains
        calls.append((vm.name, playbook_path.name))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [("agent", "opencode.yml")]


def test_install_agents_uses_forgecode_playbook(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("forgecode_main", "forgecode")])

    calls: list[tuple[str, str]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **_kwargs) -> None:
        del proxychains
        calls.append((vm.name, playbook_path.name))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [("agent", "forgecode.yml")]


def test_install_agents_uses_aider_playbook(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("aider_main", "aider")])

    calls: list[tuple[str, str]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **_kwargs) -> None:
        del proxychains
        calls.append((vm.name, playbook_path.name))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [("agent", "aider.yml")]


def test_install_agents_requires_choice_when_multiple(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("qwen", "qwen"), ("codex", "codex")])

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--config", str(config_path)])

    assert result.exit_code != 0
    assert "Provide an agent name" in result.output


def test_install_agents_without_args_prompts_interactively(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [("qwen", "qwen"), ("codex", "codex")],
        vm_names=["vm1", "vm2"],
    )

    calls: list[tuple[str, str, object]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **_kwargs) -> None:
        calls.append((vm.name, playbook_path.name, proxychains))

    class DummyQuestion:
        def __init__(self, value):
            self._value = value

        def ask(self):
            return self._value

    answers = iter(["codex", "vm2"])

    def fake_select(*_args, **_kwargs):
        return DummyQuestion(next(answers))

    monkeypatch.setattr(install_agents_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(install_agents_module.questionary, "select", fake_select)
    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [("vm2", "codex.yml", None)]


def test_install_agents_non_interactive_disables_prompts(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("qwen", "qwen"), ("codex", "codex")])

    monkeypatch.setattr(install_agents_module, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        install_agents_module.questionary,
        "select",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("prompt should not be called")),
    )

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--config", str(config_path), "--non-interactive"])

    assert result.exit_code != 0
    assert "Provide an agent name" in result.output


def test_install_agents_passes_proxychains_override(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("qwen", "qwen")])

    calls: list[tuple[str, str, object]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **_kwargs) -> None:
        calls.append((vm.name, playbook_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(
        runner,
        install_agents_command,
        ["--config", str(config_path), "--proxychains", "socks5://127.0.0.1:1080"],
    )

    assert result.exit_code == 0
    assert calls and calls[0][2] == "socks5://127.0.0.1:1080"


def test_install_agents_uses_agent_proxychains_override(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [("qwen", "qwen")],
        vm_proxychains="socks5://127.0.0.1:1080",
        agent_proxychains={"qwen": "http://10.0.0.5:3128"},
    )

    calls: list[tuple[str, str, object]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **_kwargs) -> None:
        calls.append((vm.name, playbook_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(
        runner,
        install_agents_command,
        ["--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls and calls[0][2] == "http://10.0.0.5:3128"


def test_install_agents_agent_empty_proxychains_disables_vm_proxy(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [("qwen", "qwen")],
        vm_proxychains="socks5://127.0.0.1:1080",
        agent_proxychains={"qwen": ""},
    )

    calls: list[tuple[str, str, object]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **_kwargs) -> None:
        calls.append((vm.name, playbook_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(
        runner,
        install_agents_command,
        ["--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls and calls[0][2] == ""


def test_install_agents_uses_all_bound_vms_from_vms_list(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [("qwen", "qwen")],
        vm_names=["vm1", "vm2", "vm3"],
        agent_vms={"qwen": ["vm2", "vm1"]},
    )

    calls: list[tuple[str, str, object]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **_kwargs) -> None:
        calls.append((vm.name, playbook_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(
        runner,
        install_agents_command,
        ["--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls == [("vm2", "qwen.yml", None), ("vm1", "qwen.yml", None)]


def test_install_agents_empty_vm_and_vms_installs_into_all_vms(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [("qwen", "qwen")],
        vm_names=["vm1", "vm2"],
        agent_vm={"qwen": ""},
        agent_vms={"qwen": ""},
    )

    calls: list[tuple[str, str, object]] = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **_kwargs) -> None:
        calls.append((vm.name, playbook_path.name, proxychains))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(
        runner,
        install_agents_command,
        ["--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls == [("vm1", "qwen.yml", None), ("vm2", "qwen.yml", None)]


def test_install_agents_prints_ready_message_for_single_target(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("claude", "claude")], vm_names=["agent-ubuntu"])

    class DummyProgressManager:
        def __init__(self, *, debug: bool = False):
            del debug

        def __bool__(self):
            return True

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

        def remove_task(self, task_id):
            del task_id

    monkeypatch.setattr(install_agents_module, "ProgressManager", DummyProgressManager)
    monkeypatch.setattr(install_agents_module, "_run_install_playbook", lambda *args, **kwargs: None)

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["claude", "agent-ubuntu", "--config", str(config_path)])

    assert result.exit_code == 0
    assert tr("install_agents.ready", agent_name="claude", vm_name="agent-ubuntu") in result.output


def test_install_agents_prints_summary_for_multiple_targets(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("qwen", "qwen"), ("codex", "codex")], vm_names=["vm1", "vm2"])

    class DummyProgressManager:
        def __init__(self, *, debug: bool = False):
            del debug

        def __bool__(self):
            return True

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

        def remove_task(self, task_id):
            del task_id

    monkeypatch.setattr(install_agents_module, "ProgressManager", DummyProgressManager)
    monkeypatch.setattr(install_agents_module, "_run_install_playbook", lambda *args, **kwargs: None)

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--all-agents", "--all-vms", "--config", str(config_path)])

    assert result.exit_code == 0
    assert tr("install_agents.success", count=4) in result.output


def test_install_agents_debug_uses_dummy_progress_manager(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("qwen", "qwen")])

    progress_debug_args: list[bool] = []
    calls: list[tuple[str, str, object, object, object]] = []

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

        def remove_task(self, task_id):
            del task_id

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **kwargs) -> None:
        calls.append((vm.name, playbook_path.name, proxychains, kwargs.get("progress"), kwargs.get("label")))

    monkeypatch.setattr(install_agents_module, "ProgressManager", DummyProgressManager)
    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--config", str(config_path), "--debug"])

    assert result.exit_code == 0
    assert progress_debug_args == [True]
    assert len(calls) == 1
    assert calls[0][0:2] == ("agent", "qwen.yml")
    assert calls[0][2] is None
    assert isinstance(calls[0][3], DummyProgressManager)
    assert calls[0][4] is not None


def test_log_failed_command_prints_hidden_ansible_tail(capsys):
    result = AnsiblePlaybookResult(
        ["ansible-playbook"],
        2,
        hidden_output_tail=["rc: 139", "stderr: Segmentation fault"],
    )

    install_agents_module._log_failed_command(["ansible-playbook"], result, "Installer")

    captured = capsys.readouterr()
    assert "Last hidden Ansible lines:" in captured.err
    assert "rc: 139" in captured.err
    assert "stderr: Segmentation fault" in captured.err


def test_log_failed_command_halts_progress_before_printing(capsys):
    halted = []

    class DummyProgress:
        def halt(self):
            halted.append(True)

    result = AnsiblePlaybookResult(
        ["ansible-playbook"],
        2,
        hidden_output_tail=["cmd: /bin/false"],
    )

    install_agents_module._log_failed_command(
        ["ansible-playbook"],
        result,
        "Installer",
        progress=DummyProgress(),
    )

    captured = capsys.readouterr()
    assert halted == [True]
    assert "cmd: /bin/false" in captured.err


def test_install_agents_reuses_node_setup_per_vm_within_one_run(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, [("codex_main", "codex"), ("qwen_main", "qwen")])

    calls = []

    def fake_run_install_playbook(vm, playbook_path: Path, proxychains=None, **kwargs) -> None:
        calls.append((vm.name, playbook_path.name, proxychains, kwargs.get("extra_vars_overrides")))

    monkeypatch.setattr(install_agents_module, "_run_install_playbook", fake_run_install_playbook)

    runner = CliRunner()
    result = _invoke_command(runner, install_agents_command, ["--config", str(config_path), "--all-agents"])

    assert result.exit_code == 0
    assert calls == [
        ("agent", "codex.yml", None, None),
        ("agent", "qwen.yml", None, {"skip_nvm_install": True, "skip_node_install": True}),
    ]
