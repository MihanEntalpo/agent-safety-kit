from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import yaml

pexpect = pytest.importorskip("pexpect")

from agsekit_cli.agents_modules import SUPPORTED_AGENT_TYPES
from agsekit_cli.vm_bundle_definitions import BUNDLE_DEFINITIONS

ROOT = Path(__file__).resolve().parent.parent
ENTER = "\r"
BUNDLE_ORDER = list(BUNDLE_DEFINITIONS)


@pytest.mark.skipif(os.name == "nt", reason="pexpect-based config-gen tests require a POSIX PTY")
class TestConfigGenCommand:
    def _spawn(self, config_path: Path, *, overwrite: bool = True) -> "_Wizard":
        env = os.environ.copy()
        env["AGSEKIT_LANG"] = "en"
        env["TERM"] = "xterm-256color"
        env["PYTHONUNBUFFERED"] = "1"
        env["COLUMNS"] = "120"
        env["LINES"] = "40"

        args = ["-m", "agsekit_cli.cli", "config-gen", "--config", str(config_path)]
        if overwrite:
            args.append("--overwrite")
        child = pexpect.spawn(
            sys.executable,
            args,
            cwd=str(ROOT),
            env=env,
            encoding="utf-8",
            timeout=20,
        )
        return _Wizard(child)

    def test_minimal_happy_path(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard)
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert config == {
            "vms": {
                "agent-ubuntu": {
                    "cpu": 2,
                    "ram": "4G",
                    "disk": "20G",
                }
            }
        }

    def test_vm_bundles_proxy_and_local_port_forwarding(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(
            wizard,
            bundle_names=["docker", "python"],
            proxychains="socks5://127.0.0.1:18881",
            http_proxy="http://127.0.0.1:3128",
            port_forwarding=("local", "127.0.0.1:80", "127.0.0.1:8080"),
        )
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        vm = yaml.safe_load(config_path.read_text(encoding="utf-8"))["vms"]["agent-ubuntu"]
        assert vm["install"] == sorted(["docker", "python"], key=BUNDLE_ORDER.index)
        assert vm["proxychains"] == "socks5://127.0.0.1:18881"
        assert vm["http_proxy"] == "http://127.0.0.1:3128"
        assert vm["port-forwarding"] == [
            {
                "type": "local",
                "host-addr": "127.0.0.1:8080",
                "vm-addr": "127.0.0.1:80",
            }
        ]

    def test_port_forwarding_cancel_skips_rules(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard, port_forwarding="cancel")
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        vm = yaml.safe_load(config_path.read_text(encoding="utf-8"))["vms"]["agent-ubuntu"]
        assert "port-forwarding" not in vm

    def test_remote_port_forwarding_branch(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(
            wizard,
            port_forwarding=("remote", "127.0.0.1:18881", "127.0.0.1:28881"),
        )
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        rules = yaml.safe_load(config_path.read_text(encoding="utf-8"))["vms"]["agent-ubuntu"]["port-forwarding"]
        assert rules == [
            {
                "type": "remote",
                "host-addr": "127.0.0.1:28881",
                "vm-addr": "127.0.0.1:18881",
            }
        ]

    def test_socks5_port_forwarding_branch(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard, port_forwarding=("socks5", "127.0.0.1:11800"))
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        rules = yaml.safe_load(config_path.read_text(encoding="utf-8"))["vms"]["agent-ubuntu"]["port-forwarding"]
        assert rules == [{"type": "socks5", "vm-addr": "127.0.0.1:11800"}]

    def test_multiple_port_forwarding_rules_are_collected(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(
            wizard,
            port_forwarding=[
                ("local", "127.0.0.1:80", "127.0.0.1:8080"),
                ("socks5", "127.0.0.1:11800"),
            ],
        )
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        rules = yaml.safe_load(config_path.read_text(encoding="utf-8"))["vms"]["agent-ubuntu"]["port-forwarding"]
        assert rules == [
            {
                "type": "local",
                "host-addr": "127.0.0.1:8080",
                "vm-addr": "127.0.0.1:80",
            },
            {
                "type": "socks5",
                "vm-addr": "127.0.0.1:11800",
            },
        ]

    def test_multi_vm_agent_assignment_updates_both_sides(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard, add_more=True)
        _fill_vm_minimal(wizard, name="vm-2")
        _add_agent(
            wizard,
            agent_type="qwen",
            name="qwen",
            vm_toggles=[1],
        )
        wizard.confirm("Add another agent?", False)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert config["agents"]["qwen"]["vms"] == ["agent-ubuntu"]
        assert config["vms"]["agent-ubuntu"]["allowed_agents"] == ["qwen"]
        assert "allowed_agents" not in config["vms"]["vm-2"]

    def test_second_vm_uses_next_available_default_name(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard, add_more=True)
        _fill_vm_minimal(wizard)
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert list(config["vms"].keys()) == ["agent-ubuntu", "agent-ubuntu-2"]

    def test_duplicate_vm_name_is_rejected_and_reprompted(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard, add_more=True)
        wizard.text("VM name", "agent-ubuntu", clear_default=True)
        wizard.expect("VM name `agent-ubuntu` is already used. Enter a different name.")
        wizard.text("VM name", "custom-vm", clear_default=True)
        wizard.text("How many vCPUs to allocate", "")
        wizard.text("RAM size", "")
        wizard.text("Disk size", "")
        wizard.checkbox("Select install bundles for this VM", toggles=[], ready_text=BUNDLE_ORDER[-1])
        wizard.text("Proxychains proxy URL", "")
        wizard.text("VM HTTP proxy URL", "")
        wizard.confirm("Configure port-forwarding for this VM?", False)
        wizard.confirm("Add another VM?", False)
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert list(config["vms"].keys()) == ["agent-ubuntu", "custom-vm"]

    def test_agent_env_and_default_args(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard)
        _add_agent(
            wizard,
            agent_type="qwen",
            name="qwen",
            env_lines=["OPENAI_API_KEY=abc", "EMPTY="],
            default_args="--model gpt-5 --dangerously-bypass-approvals-and-sandbox",
        )
        wizard.confirm("Add another agent?", False)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        agent = yaml.safe_load(config_path.read_text(encoding="utf-8"))["agents"]["qwen"]
        assert agent["env"] == {"OPENAI_API_KEY": "abc", "EMPTY": ""}
        assert agent["default-args"] == [
            "--model",
            "gpt-5",
            "--dangerously-bypass-approvals-and-sandbox",
        ]

    def test_agent_proxy_override_semantics(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard, add_more=True)
        _fill_vm_minimal(wizard, name="vm-2")
        _add_agent(
            wizard,
            agent_type="qwen",
            name="inherit",
            vm_toggles=[],
            proxychains="",
            http_proxy="",
        )
        wizard.confirm("Add another agent?", True)
        _add_agent(
            wizard,
            agent_type="codex",
            name="disable",
            vm_toggles=[],
            proxychains='""',
            http_proxy='""',
        )
        wizard.confirm("Add another agent?", True)
        _add_agent(
            wizard,
            agent_type="claude",
            name="override",
            vm_toggles=[],
            proxychains="socks5://127.0.0.1:9000",
            http_proxy="http://127.0.0.1:9001",
        )
        wizard.confirm("Add another agent?", False)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        agents = yaml.safe_load(config_path.read_text(encoding="utf-8"))["agents"]
        assert "proxychains" not in agents["inherit"]
        assert "http_proxy" not in agents["inherit"]
        assert agents["disable"]["proxychains"] == ""
        assert agents["disable"]["http_proxy"] == ""
        assert agents["override"]["proxychains"] == "socks5://127.0.0.1:9000"
        assert agents["override"]["http_proxy"] == "http://127.0.0.1:9001"

    def test_cancel_after_existing_agent_stops_without_extra_agent(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard)
        _add_agent(wizard, agent_type="qwen", name="qwen")
        wizard.confirm("Add another agent?", True)
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert list(config["agents"].keys()) == ["qwen"]

    def test_second_agent_uses_next_available_default_name(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard)
        _add_agent(wizard, agent_type="codex", name="codex")
        wizard.confirm("Add another agent?", True)
        _add_agent(wizard, agent_type="codex", name="")
        wizard.confirm("Add another agent?", False)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert list(config["agents"].keys()) == ["codex", "codex-2"]

    def test_duplicate_agent_name_is_rejected_and_reprompted(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard)
        _add_agent(wizard, agent_type="qwen", name="qwen")
        wizard.confirm("Add another agent?", True)
        wizard.select("Agent type", index=SUPPORTED_AGENT_TYPES.index("qwen"), ready_text=SUPPORTED_AGENT_TYPES[-1])
        wizard.text("Agent name", "qwen", clear_default=True)
        wizard.expect("Agent name `qwen` is already used. Enter a different name.")
        wizard.text("Agent name", "qwen-alt", clear_default=True)
        wizard.confirm("Define environment variables for this agent?", False)
        wizard.confirm("Define default CLI arguments for this agent?", False)
        wizard.text("Agent proxychains URL", "")
        wizard.text("Agent HTTP proxy override", "")
        wizard.confirm("Add another agent?", False)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert list(config["agents"].keys()) == ["qwen", "qwen-alt"]

    def test_mount_without_agents_skips_restrictions_and_creates_backupignore(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard)
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", True)
        wizard.text("Source directory path", str(source_dir))
        wizard.text("Directory inside VM", "")
        wizard.text("Backup directory", "")
        wizard.confirm("Create a default .backupignore file in the source directory?", True)
        wizard.confirm("Add another mount?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        mount = config["mounts"][0]
        assert mount == {
            "source": str(source_dir),
            "target": f"/home/ubuntu/{source_dir.name}",
            "backup": str(source_dir.parent / f"backups-{source_dir.name}"),
            "vm": "agent-ubuntu",
        }
        ignore_path = source_dir / ".backupignore"
        assert ignore_path.exists()
        assert "venv/" in ignore_path.read_text(encoding="utf-8")
        assert "node_modules/" in ignore_path.read_text(encoding="utf-8")

    def test_mount_with_multi_vm_and_restricted_agents(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        source_dir = tmp_path / "worktree"
        source_dir.mkdir()
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard, add_more=True)
        _fill_vm_minimal(wizard, name="vm-2")
        _add_agent(wizard, agent_type="qwen", name="qwen", vm_toggles=[])
        wizard.confirm("Add another agent?", True)
        _add_agent(wizard, agent_type="codex", name="codex", vm_toggles=[])
        wizard.confirm("Add another agent?", False)
        wizard.confirm("Do you want to configure mounts?", True)
        wizard.text("Source directory path", str(source_dir))
        wizard.text("Directory inside VM", "")
        wizard.text("Backup directory", "")
        wizard.text("Which VM should be used for this mount?", "vm-2")
        wizard.checkbox("Allowed agents for this mount", toggles=[0, 1])
        wizard.confirm("Create a default .backupignore file in the source directory?", False)
        wizard.confirm("Add another mount?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        mount = config["mounts"][0]
        assert mount["vm"] == "vm-2"
        assert mount["allowed_agents"] == ["qwen"]
        assert not (source_dir / ".backupignore").exists()

    def test_existing_backupignore_is_preserved(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        ignore_path = source_dir / ".backupignore"
        ignore_path.write_text("custom-rule/\n", encoding="utf-8")
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard)
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", True)
        wizard.text("Source directory path", str(source_dir))
        wizard.text("Directory inside VM", "")
        wizard.text("Backup directory", "")
        wizard.confirm("Create a default .backupignore file in the source directory?", True)
        wizard.confirm("Add another mount?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        assert ignore_path.read_text(encoding="utf-8") == "custom-rule/\n"

    def test_global_settings_customization(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        ssh_dir = tmp_path / "ssh"
        env_dir = tmp_path / "env"
        wizard = self._spawn(config_path)

        _fill_vm_minimal(wizard)
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", True)
        wizard.text("SSH keys folder override", str(ssh_dir))
        wizard.text("systemd.env folder override", str(env_dir))
        wizard.text("How often should portforward reload the config", "21", clear_default=True)
        wizard.text("HTTP proxy auto-port pool start", "48100", clear_default=True)
        wizard.text("HTTP proxy auto-port pool end", "48200", clear_default=True)
        wizard.text("Where should the config be saved?", "")
        wizard.finish()

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert config["global"] == {
            "ssh_keys_folder": str(ssh_dir),
            "systemd_env_folder": str(env_dir),
            "portforward_config_check_interval_sec": 21,
            "http_proxy_port_pool": {"start": 48100, "end": 48200},
        }

    def test_existing_destination_without_overwrite_is_refused(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text("original: true\n", encoding="utf-8")
        wizard = self._spawn(config_path, overwrite=False)

        _fill_vm_minimal(wizard)
        _cancel_agents(wizard)
        wizard.confirm("Do you want to configure mounts?", False)
        wizard.confirm("Customize global agsekit settings?", False)
        wizard.text("Where should the config be saved?", "")
        output = wizard.finish()

        assert "Configuration file already exists" in output
        assert config_path.read_text(encoding="utf-8") == "original: true\n"


class _Wizard:
    def __init__(self, child: "pexpect.spawn") -> None:
        self.child = child

    def text(self, prompt: str, answer: str, *, clear_default: bool = False) -> None:
        self.child.expect_exact(prompt)
        if clear_default:
            self.child.send("\x15")
        self.child.sendline(answer)

    def confirm(self, prompt: str, answer: bool) -> None:
        self.child.expect_exact(prompt)
        self.child.send("y" if answer else "n")

    def checkbox(self, prompt: str, *, toggles: List[int], ready_text: str | None = None) -> None:
        self.child.expect_exact(prompt)
        if ready_text is not None:
            self.child.expect_exact(ready_text)
        current = 0
        for toggle in toggles:
            while current < toggle:
                self.child.send("j")
                current += 1
            self.child.send(" ")
        self.child.send(ENTER)

    def select(self, prompt: str, *, index: int, ready_text: str | None = None) -> None:
        self.child.expect_exact(prompt)
        if ready_text is not None:
            self.child.expect_exact(ready_text)
        for _ in range(index):
            self.child.send("j")
        self.child.send(ENTER)

    def expect(self, text: str) -> None:
        self.child.expect_exact(text)

    def finish(self) -> str:
        self.child.expect(pexpect.EOF)
        self.child.close()
        assert self.child.exitstatus == 0, self.child.before
        return self.child.before


def _fill_vm_minimal(
    wizard: _Wizard,
    *,
    name: str = "",
    bundle_names: Optional[List[str]] = None,
    proxychains: str = "",
    http_proxy: str = "",
    port_forwarding: object = None,
    add_more: bool = False,
) -> None:
    bundle_names = bundle_names or []
    wizard.text("VM name", name, clear_default=bool(name))
    wizard.text("How many vCPUs to allocate", "")
    wizard.text("RAM size", "")
    wizard.text("Disk size", "")
    bundle_order = list(BUNDLE_DEFINITIONS.keys())
    wizard.checkbox(
        "Select install bundles for this VM",
        toggles=sorted(bundle_order.index(name) for name in bundle_names),
        ready_text=bundle_order[-1],
    )
    wizard.text("Proxychains proxy URL", proxychains)
    wizard.text("VM HTTP proxy URL", http_proxy)
    if port_forwarding is None:
        wizard.confirm("Configure port-forwarding for this VM?", False)
    else:
        wizard.confirm("Configure port-forwarding for this VM?", True)
        if port_forwarding == "cancel":
            wizard.text("Port-forwarding type", "Cancel")
        else:
            rules = port_forwarding if isinstance(port_forwarding, list) else [port_forwarding]
            for index, rule in enumerate(rules):
                pf_type = rule[0]
                wizard.text("Port-forwarding type", pf_type)
                wizard.text("VM address for port-forwarding", rule[1])
                if pf_type != "socks5":
                    wizard.text("Host address for port-forwarding", rule[2])
                wizard.confirm("Add another port-forwarding rule?", index < len(rules) - 1)
    wizard.confirm("Add another VM?", add_more)


def _cancel_agents(wizard: _Wizard) -> None:
    wizard.select("Agent type", index=len(SUPPORTED_AGENT_TYPES), ready_text=SUPPORTED_AGENT_TYPES[-1])


def _add_agent(
    wizard: _Wizard,
    *,
    agent_type: str,
    name: str,
    env_lines: Optional[List[str]] = None,
    default_args: Optional[str] = None,
    vm_toggles: Optional[List[int]] = None,
    proxychains: str = "",
    http_proxy: str = "",
) -> None:
    agent_order = list(SUPPORTED_AGENT_TYPES)
    assert agent_type in agent_order
    wizard.select("Agent type", index=agent_order.index(agent_type), ready_text=agent_order[-1])
    wizard.text("Agent name", name, clear_default=bool(name))
    if env_lines:
        wizard.confirm("Define environment variables for this agent?", True)
        for line in env_lines:
            wizard.text("Environment variable as KEY=VALUE", line)
        wizard.text("Environment variable as KEY=VALUE", "")
    else:
        wizard.confirm("Define environment variables for this agent?", False)

    if default_args is not None:
        wizard.confirm("Define default CLI arguments for this agent?", True)
        wizard.text("Default arguments as one line", default_args)
    else:
        wizard.confirm("Define default CLI arguments for this agent?", False)

    if vm_toggles is not None:
        wizard.checkbox("Which VMs should this agent be assigned to?", toggles=vm_toggles)

    wizard.text("Agent proxychains URL", proxychains)
    wizard.text("Agent HTTP proxy override", http_proxy)
