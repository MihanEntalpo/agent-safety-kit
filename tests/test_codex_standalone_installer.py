from pathlib import Path
import os
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_codex_playbook_uses_official_standalone_package() -> None:
    playbook_path = ROOT / "agsekit_cli" / "ansible" / "agents" / "codex.yml"
    content = playbook_path.read_text(encoding="utf-8")
    playbook = yaml.safe_load(content)
    tasks = playbook[1]["tasks"]

    assert "https://chatgpt.com/codex/install.sh" in content
    assert "CODEX_NON_INTERACTIVE=1" in content
    assert "CODEX_RELEASE={{ requested_agent_version or 'latest' }}" in content
    assert "npm install -g @openai/codex" not in content

    package_check = next(
        task for task in tasks if task["name"] == "Verify official Codex standalone package files"
    )
    checked_paths = package_check["loop"]
    assert "{{ codex_package_root }}/codex-package.json" in checked_paths
    assert "{{ codex_package_root }}/bin/codex-code-mode-host" in checked_paths
    assert "{{ codex_package_root }}/codex-path/rg" in checked_paths
    assert "{{ codex_package_root }}/codex-resources/bwrap" in checked_paths


def test_codex_shell_installer_uses_official_standalone_package() -> None:
    installer = ROOT / "agsekit_cli" / "agent_scripts" / "codex.sh"
    content = installer.read_text(encoding="utf-8")

    assert "https://chatgpt.com/codex/install.sh" in content
    assert "CODEX_NON_INTERACTIVE=1" in content
    assert 'CODEX_RELEASE="$CODEX_RELEASE"' in content
    assert "codex-package.json" in content
    assert "codex-code-mode-host" in content
    assert "npm install" not in content


def test_http_proxy_runner_exports_http_websocket_and_no_proxy_variables() -> None:
    runner = ROOT / "agsekit_cli" / "run_with_http_proxy.sh"
    proxy_url = "http://127.0.0.1:18081"
    keys = [
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "WS_PROXY",
        "ws_proxy",
        "WSS_PROXY",
        "wss_proxy",
        "NO_PROXY",
        "no_proxy",
    ]
    command = [
        "bash",
        str(runner),
        "--url",
        proxy_url,
        "--",
        "python",
        "-c",
        "import os; print('\\n'.join(os.environ.get(key, '') for key in " + repr(keys) + "))",
    ]
    env = dict(os.environ)
    env["NO_PROXY"] = "example.test"
    env["no_proxy"] = "example.test"

    result = subprocess.run(command, check=True, capture_output=True, text=True, env=env)
    values = result.stdout.splitlines()

    assert values[:10] == [proxy_url] * 10
    assert values[10] == "localhost,127.0.0.1,::1,example.test"
    assert values[11] == "localhost,127.0.0.1,::1,example.test"


def test_http_proxy_runner_restarts_and_stops_codex_daemon(tmp_path: Path) -> None:
    runner = ROOT / "agsekit_cli" / "run_with_http_proxy.sh"
    calls_path = tmp_path / "calls"
    codex_path = tmp_path / "codex"
    codex_path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$*\" >> {calls_path}\n",
        encoding="utf-8",
    )
    codex_path.chmod(0o755)

    subprocess.run(
        [
            "bash",
            str(runner),
            "--url",
            "http://127.0.0.1:18081",
            "--",
            str(codex_path),
            "exec",
            "proxy test",
        ],
        check=True,
    )

    assert calls_path.read_text(encoding="utf-8").splitlines() == [
        "app-server daemon restart",
        "exec proxy test",
        "app-server daemon stop",
    ]
