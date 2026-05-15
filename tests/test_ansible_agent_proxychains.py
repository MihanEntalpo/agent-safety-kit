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
    task_names = [item["name"] for item in enable_block]
    prefix_task = next(item for item in enable_block if item["name"] == "Set proxychains command prefix")

    assert "Install proxychains" not in task_names
    assert prefix_task["ansible.builtin.set_fact"]["proxychains_prefix"] == "proxychains4 -q -f /tmp/agsekit-proxychains.conf "

    disable_task = tasks[1]
    disable_facts = disable_task["ansible.builtin.set_fact"]
    assert disable_facts["proxychains_prefix"] == ""


def test_claude_installer_tasks_run_via_proxychains_prefix():
    playbook = _load_yaml(Path("agsekit_cli/ansible/agents/claude.yml"))
    tasks = playbook[1]["tasks"]

    install_task = next(item for item in tasks if item["name"] == "Install Claude Code CLI")
    verify_task = next(item for item in tasks if item["name"] == "Verify Claude CLI after installation")

    assert install_task["ansible.builtin.command"].startswith("{{ proxychains_prefix }}bash -lc ")
    assert "@anthropic-ai/claude-code@{{ requested_agent_version }}" in install_task["ansible.builtin.command"]
    assert "environment" not in install_task
    assert "claude --version" in verify_task["ansible.builtin.command"]


def test_cline_installer_tasks_run_via_proxychains_prefix():
    playbook = _load_yaml(Path("agsekit_cli/ansible/agents/cline.yml"))
    tasks = playbook[1]["tasks"]

    install_task = next(item for item in tasks if item["name"] == "Install cline CLI")
    uninstall_task = next(item for item in tasks if item["name"] == "Remove existing cline CLI before reinstall")

    assert install_task["ansible.builtin.command"].startswith("{{ proxychains_prefix }}bash -lc ")
    assert "npm install -g cline@{{ requested_agent_version }}" in install_task["ansible.builtin.command"]
    assert "environment" not in install_task
    assert "npm uninstall -g cline" in uninstall_task["ansible.builtin.command"]


def test_opencode_installer_tasks_run_via_proxychains_prefix():
    playbook = _load_yaml(Path("agsekit_cli/ansible/agents/opencode.yml"))
    tasks = playbook[1]["tasks"]

    install_task = next(item for item in tasks if item["name"] == "Install OpenCode CLI")
    uninstall_task = next(item for item in tasks if item["name"] == "Remove existing OpenCode CLI before reinstall")
    verify_task = next(item for item in tasks if item["name"] == "Verify OpenCode CLI after installation")

    assert install_task["ansible.builtin.command"].startswith("{{ proxychains_prefix }}bash -lc ")
    assert "npm install -g opencode-ai@{{ requested_agent_version }}" in install_task["ansible.builtin.command"]
    assert "environment" not in install_task
    assert "npm uninstall -g opencode-ai" in uninstall_task["ansible.builtin.command"]
    assert "opencode --version" in verify_task["ansible.builtin.command"]


def test_forgecode_installer_tasks_run_via_proxychains_prefix():
    playbook = _load_yaml(Path("agsekit_cli/ansible/agents/forgecode.yml"))
    tasks = playbook[1]["tasks"]

    download_task = next(item for item in tasks if item["name"] == "Download CodeForge installer")
    run_task = next(item for item in tasks if item["name"] == "Run CodeForge installer")
    publish_task = next(item for item in tasks if item["name"] == "Publish Forge binary into VM PATH")
    verify_task = next(item for item in tasks if item["name"] == "Verify CodeForge CLI after installation")

    assert download_task["ansible.builtin.command"].startswith("{{ proxychains_prefix }}curl ")
    assert run_task["ansible.builtin.command"] == "{{ proxychains_prefix }}bash /tmp/forgecode-install.sh {{ requested_agent_version }}"
    assert "environment" not in download_task
    assert "environment" not in run_task
    assert publish_task["ansible.builtin.shell"].strip().startswith("set -euo pipefail")
    assert "$HOME/.local/bin/forge" in publish_task["ansible.builtin.shell"]
    assert "/usr/local/bin/forge" in publish_task["ansible.builtin.shell"]
    assert verify_task["ansible.builtin.command"] == "forge --version"


def test_aider_installer_tasks_run_via_proxychains_prefix():
    playbook = _load_yaml(Path("agsekit_cli/ansible/agents/aider.yml"))
    tasks = playbook[1]["tasks"]

    uv_task = next(item for item in tasks if item["name"] == "Install uv for aider")
    run_task = next(item for item in tasks if item["name"] == "Install aider CLI")
    uninstall_task = next(item for item in tasks if item["name"] == "Remove existing aider installation before reinstall")
    publish_task = next(item for item in tasks if item["name"] == "Publish aider binary into VM PATH")
    verify_task = next(item for item in tasks if item["name"] == "Verify aider CLI after installation")

    assert uv_task["ansible.builtin.command"].startswith("{{ proxychains_prefix }}bash -lc ")
    assert "python3 -m pip install --user --break-system-packages uv" in uv_task["ansible.builtin.command"]
    assert run_task["ansible.builtin.command"].startswith("{{ proxychains_prefix }}bash -lc ")
    assert "$HOME/.local/bin/uv tool install --python 3.12" in run_task["ansible.builtin.command"]
    assert "aider-chat=={{ requested_agent_version }}" in run_task["ansible.builtin.command"]
    assert "environment" not in run_task
    assert '"$HOME/.local/bin/uv" tool uninstall aider' in uninstall_task["ansible.builtin.shell"]
    assert publish_task["ansible.builtin.shell"].strip().startswith("set -euo pipefail")
    assert "$HOME/.local/bin/aider" in publish_task["ansible.builtin.shell"]
    assert "/usr/local/bin/aider" in publish_task["ansible.builtin.shell"]
    assert verify_task["ansible.builtin.command"] == "aider --version"


def test_codex_glibc_prebuilt_installer_tasks_run_via_proxychains_prefix():
    playbook = _load_yaml(Path("agsekit_cli/ansible/agents/codex-glibc-prebuilt.yml"))
    tasks = playbook[1]["tasks"]

    arch_task = next(item for item in tasks if item["name"] == "Determine codex-glibc prebuilt architecture")
    resolve_task = next(
        item for item in tasks if item["name"] == "Resolve codex-glibc prebuilt release metadata for VM architecture"
    )
    download_task = next(item for item in tasks if item["name"] == "Download codex-glibc prebuilt archive")
    verify_task = next(item for item in tasks if item["name"] == "Verify codex-glibc-prebuilt binary works")

    assert "ansible_architecture" in arch_task["ansible.builtin.set_fact"]["codex_prebuilt_arch"]
    assert "delegate_to" not in resolve_task
    assert "connection" not in resolve_task
    assert "ansible.builtin.command" not in resolve_task
    resolve_fact = resolve_task["ansible.builtin.set_fact"]["codex_glibc_prebuilt_meta"]
    assert "lookup(" in resolve_fact
    assert "'pipe'" in resolve_fact
    assert "agsekit_cli.prebuilt resolve-codex-glibc-prebuilt --arch" in resolve_fact
    assert "--tag" in resolve_fact
    assert "ansible_playbook_python" in resolve_fact
    assert "codex_prebuilt_arch" in resolve_fact
    assert download_task["ansible.builtin.command"].startswith("{{ proxychains_prefix }}curl ")
    assert "environment" not in download_task
    assert verify_task["ansible.builtin.command"] == "{{ codex_install_path }} --version"
