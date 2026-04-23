from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_codex_logrotate_shared_tasks_install_expected_policy() -> None:
    task_file = ROOT / "agsekit_cli" / "ansible" / "agents" / "codex_logrotate.yml"
    tasks = _load_yaml(task_file)

    install_task = next(item for item in tasks if item["name"] == "Install logrotate")
    config_task = next(item for item in tasks if item["name"] == "Install Codex TUI logrotate config")

    assert install_task["ansible.builtin.apt"]["name"] == "logrotate"
    assert install_task["become"] is True

    content = config_task["ansible.builtin.copy"]["content"]
    assert "{{ ansible_env.HOME }}/.codex/log/codex-tui.log {" in content
    assert "size 100M" in content
    assert "rotate 10" in content
    assert "compress" in content
    assert "delaycompress" in content
    assert "missingok" in content
    assert "notifempty" in content
    assert "copytruncate" in content
    assert "su {{ ansible_user | default(ansible_env.USER) }} {{ ansible_user | default(ansible_env.USER) }}" in content
    assert config_task["become"] is True


def test_codex_installers_include_shared_logrotate_tasks() -> None:
    playbooks = [
        ROOT / "agsekit_cli" / "ansible" / "agents" / "codex.yml",
        ROOT / "agsekit_cli" / "ansible" / "agents" / "codex-glibc.yml",
        ROOT / "agsekit_cli" / "ansible" / "agents" / "codex-glibc-prebuilt.yml",
    ]

    for playbook_path in playbooks:
        playbook = _load_yaml(playbook_path)
        tasks = playbook[1]["tasks"]
        include_task = next(item for item in tasks if item["name"] == "Configure Codex logrotate")
        assert include_task["ansible.builtin.include_tasks"] == "{{ playbook_dir }}/codex_logrotate.yml"
