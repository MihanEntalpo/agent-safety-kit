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


def test_cline_installer_tasks_run_via_proxychains_prefix():
    playbook = _load_yaml(Path("agsekit_cli/ansible/agents/cline.yml"))
    tasks = playbook[1]["tasks"]

    install_task = next(item for item in tasks if item["name"] == "Install cline CLI")
    check_task = next(item for item in tasks if item["name"] == "Check cline CLI installation")

    assert install_task["ansible.builtin.command"].startswith("{{ proxychains_prefix }}bash -lc ")
    assert "npm install -g cline@latest" in install_task["ansible.builtin.command"]
    assert "environment" not in install_task
    assert "npm list -g --depth=0 cline" in check_task["ansible.builtin.command"]


def test_opencode_installer_tasks_run_via_proxychains_prefix():
    playbook = _load_yaml(Path("agsekit_cli/ansible/agents/opencode.yml"))
    tasks = playbook[1]["tasks"]

    install_task = next(item for item in tasks if item["name"] == "Install OpenCode CLI")
    check_task = next(item for item in tasks if item["name"] == "Check OpenCode CLI installation")
    verify_task = next(item for item in tasks if item["name"] == "Verify OpenCode CLI after installation")

    assert install_task["ansible.builtin.command"].startswith("{{ proxychains_prefix }}bash -lc ")
    assert "npm install -g opencode-ai@latest" in install_task["ansible.builtin.command"]
    assert "environment" not in install_task
    assert "npm list -g --depth=0 opencode-ai" in check_task["ansible.builtin.command"]
    assert "opencode --version" in verify_task["ansible.builtin.command"]


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
    assert resolve_task["delegate_to"] == "localhost"
    assert resolve_task["connection"] == "local"
    assert resolve_task["vars"]["ansible_python_interpreter"] == "{{ ansible_playbook_python }}"
    assert resolve_task["ansible.builtin.command"]["argv"][-2:] == ["--arch", "{{ codex_prebuilt_arch }}"]
    assert download_task["ansible.builtin.command"].startswith("{{ proxychains_prefix }}curl ")
    assert "environment" not in download_task
    assert verify_task["ansible.builtin.command"] == "{{ codex_install_path }} --version"
