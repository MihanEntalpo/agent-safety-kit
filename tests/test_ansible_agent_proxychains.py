from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_proxychains_tasks_define_only_command_prefix():
    tasks = _load_yaml(Path("agsekit_cli/ansible/agents/proxychains.yml"))

    enable_task = tasks[0]
    enable_block = enable_task["block"]
    prefix_task = next(item for item in enable_block if item["name"] == "Set proxychains command prefix")

    assert prefix_task["ansible.builtin.set_fact"]["proxychains_prefix"] == "proxychains4 -q -f /tmp/agsekit-proxychains.conf "

    disable_task = tasks[1]
    disable_facts = disable_task["ansible.builtin.set_fact"]
    assert disable_facts["proxychains_prefix"] == ""


def test_claude_installer_tasks_run_via_proxychains_prefix():
    playbook = _load_yaml(Path("agsekit_cli/ansible/agents/claude.yml"))
    tasks = playbook[1]["tasks"]

    download_task = next(item for item in tasks if item["name"] == "Download Claude Code installer")
    run_task = next(item for item in tasks if item["name"] == "Run Claude Code installer")
    fallback_task = next(item for item in tasks if item["name"] == "Fallback install Claude binary from downloaded cache")
    verify_task = next(item for item in tasks if item["name"] == "Verify Claude CLI after installation")

    assert download_task["ansible.builtin.command"].startswith("{{ proxychains_prefix }}curl ")
    assert run_task["ansible.builtin.command"] == "{{ proxychains_prefix }}bash /tmp/claude-install.sh"
    assert "environment" not in download_task
    assert "environment" not in run_task
    assert run_task["failed_when"] is False
    assert "claude_install.rc != 0" in fallback_task["when"]
    assert verify_task["ansible.builtin.command"] == "claude --version"
