from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_node_agent_playbooks_resolve_latest_major_version() -> None:
    playbooks = [
        ROOT / "agsekit_cli" / "ansible" / "agents" / "cline.yml",
        ROOT / "agsekit_cli" / "ansible" / "agents" / "codex.yml",
        ROOT / "agsekit_cli" / "ansible" / "agents" / "opencode.yml",
        ROOT / "agsekit_cli" / "ansible" / "agents" / "qwen.yml",
    ]

    for playbook in playbooks:
        content = playbook.read_text(encoding="utf-8")
        assert "nvm ls-remote" in content, playbook.name
        assert "nvm use --silent default" in content, playbook.name
        assert 'nvm install {{ node_version }}' not in content, playbook.name
        assert 'nvm alias default {{ node_version }}' not in content, playbook.name
        assert "ansible.builtin.command: node -v" not in content, playbook.name


def test_node_agent_shell_installers_resolve_latest_major_version() -> None:
    scripts = [
        ROOT / "agsekit_cli" / "agent_scripts" / "codex.sh",
        ROOT / "agsekit_cli" / "agent_scripts" / "qwen.sh",
    ]

    for script in scripts:
        content = script.read_text(encoding="utf-8")
        assert "resolve_latest_node_major" in content, script.name
        assert "nvm ls-remote" in content, script.name
        assert "nvm install 24" not in content, script.name
