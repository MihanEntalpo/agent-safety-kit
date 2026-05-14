from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_node_agent_playbooks_resolve_current_lts_version() -> None:
    playbooks = [
        ROOT / "agsekit_cli" / "ansible" / "agents" / "cline.yml",
        ROOT / "agsekit_cli" / "ansible" / "agents" / "codex.yml",
        ROOT / "agsekit_cli" / "ansible" / "agents" / "opencode.yml",
        ROOT / "agsekit_cli" / "ansible" / "agents" / "qwen.yml",
    ]

    for playbook in playbooks:
        content = playbook.read_text(encoding="utf-8")
        assert "nvm version-remote --lts" in content, playbook.name
        assert "nvm ls-remote" not in content, playbook.name
        assert "nvm use --silent default" in content, playbook.name
        assert 'nvm install "$resolved_version"' in content, playbook.name
        assert 'nvm alias default "$resolved_version"' in content, playbook.name
        assert "ansible.builtin.command: node -v" not in content, playbook.name
        assert 'node_version: "24"' not in content, playbook.name


def test_node_agent_shell_installers_resolve_current_lts_version() -> None:
    scripts = [
        ROOT / "agsekit_cli" / "agent_scripts" / "codex.sh",
        ROOT / "agsekit_cli" / "agent_scripts" / "qwen.sh",
    ]

    for script in scripts:
        content = script.read_text(encoding="utf-8")
        assert "resolve_current_lts_node" in content, script.name
        assert "nvm version-remote --lts" in content, script.name
        assert "nvm ls-remote" not in content, script.name
        assert "nvm install 24" not in content, script.name


def test_nodejs_bundle_installs_exact_lts_and_skips_reinstall_when_node_exists() -> None:
    playbook = ROOT / "agsekit_cli" / "ansible" / "bundles" / "nodejs.yml"
    script = ROOT / "agsekit_cli" / "vm_installers" / "nodejs.sh"

    playbook_content = playbook.read_text(encoding="utf-8")
    script_content = script.read_text(encoding="utf-8")

    assert "nvm version-remote --lts" in playbook_content
    assert 'nvm alias default "$resolved_version"' in playbook_content
    assert 'nvm alias default "lts/*"' not in playbook_content
    assert 'when: (node_version != "lts") or node_check.rc != 0' in playbook_content

    assert 'VERSION="${1:-lts}"' in script_content
    assert "nvm version-remote --lts" in script_content
    assert 'nvm alias default "$RESOLVED_VERSION"' in script_content
    assert 'nvm alias default "lts/*"' not in script_content
    assert "Node.js is already installed, keeping the current version." in script_content
