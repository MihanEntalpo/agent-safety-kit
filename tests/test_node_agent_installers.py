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
        assert "requested_agent_version or 'latest'" in content, playbook.name


def test_agent_playbooks_do_not_define_hardcoded_default_versions() -> None:
    agents_dir = ROOT / "agsekit_cli" / "ansible" / "agents"
    agent_playbooks = sorted(
        playbook
        for playbook in agents_dir.glob("*.yml")
        if playbook.name not in {"proxychains.yml", "codex_logrotate.yml"}
    )

    for playbook in agent_playbooks:
        content = playbook.read_text(encoding="utf-8")
        assert "default_agent_version" not in content, playbook.name
        assert 'requested_agent_version: "{{ agent_version }}"' in content, playbook.name


def test_codex_glibc_builders_patch_upstream_recursion_limit() -> None:
    builder_script = (
        ROOT / "prebuilt-agents" / "codex-glibc" / "build-codex-glibc.sh"
    ).read_text(encoding="utf-8")
    agent_script = (ROOT / "agsekit_cli" / "agent_scripts" / "codex-glibc.sh").read_text(encoding="utf-8")
    playbook = (ROOT / "agsekit_cli" / "ansible" / "agents" / "codex-glibc.yml").read_text(encoding="utf-8")

    for content in (builder_script, agent_script, playbook):
        assert '#![recursion_limit = "256"]' in content
        assert "codex-exec" in content


def test_codex_glibc_builders_pin_rust_toolchain() -> None:
    version_file = ROOT / "agsekit_cli" / "codex_rust_toolchain_version.txt"
    dockerfile = (ROOT / "prebuilt-agents" / "codex-glibc" / "Dockerfile").read_text(encoding="utf-8")
    build_wrapper = (ROOT / "prebuilt-agents" / "codex-glibc" / "build.sh").read_text(encoding="utf-8")
    builder_script = (ROOT / "prebuilt-agents" / "codex-glibc" / "build-codex-glibc.sh").read_text(encoding="utf-8")
    agent_script = (ROOT / "agsekit_cli" / "agent_scripts" / "codex-glibc.sh").read_text(encoding="utf-8")
    playbook = (ROOT / "agsekit_cli" / "ansible" / "agents" / "codex-glibc.yml").read_text(encoding="utf-8")

    version = version_file.read_text(encoding="utf-8").strip()

    assert version.count(".") == 2
    assert all(part.isdigit() for part in version.split("."))
    assert "ARG RUST_TOOLCHAIN_VERSION" in dockerfile
    assert "--default-toolchain \"${RUST_TOOLCHAIN_VERSION}\"" in dockerfile
    assert "codex_rust_toolchain_version.txt" in build_wrapper
    assert "RUST_TOOLCHAIN_VERSION" in build_wrapper
    assert "RUST_TOOLCHAIN_VERSION" in builder_script
    assert "codex_rust_toolchain_version.txt" in agent_script
    assert "RUST_TOOLCHAIN" in agent_script
    assert "codex_rust_toolchain_version.txt" in playbook
    assert "rust_toolchain" in playbook


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
