from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from tests.integration.utils import REPO_ROOT, clean_env, random_vm_name, require_host_tools, run_cli, run_cmd, write_config


pytestmark = pytest.mark.host_integration
pexpect = pytest.importorskip("pexpect")


def _skip_if_multipass_unusable() -> None:
    check = run_cmd(["multipass", "version"], check=False)
    stderr = (check.stderr or "").strip()
    stdout = (check.stdout or "").strip()
    details = "\n".join(part for part in (stderr, stdout) if part)
    markers = (
        "execv failed",
        "snap-confine is packaged without necessary permissions",
    )
    if any(marker in details for marker in markers):
        pytest.skip("multipass is installed but not executable in this environment")
    if check.returncode != 0:
        pytest.skip(details or "multipass is not ready")


def _instance_exists(name: str) -> bool:
    result = run_cmd(["multipass", "list", "--format", "json"])
    return f'"name":"{name}"' in result.stdout.replace(" ", "")


def _delete_if_exists(name: str) -> None:
    if not _instance_exists(name):
        return
    run_cmd(["multipass", "delete", name], check=False)
    run_cmd(["multipass", "purge"], check=False)


def _vm_bash(vm_name: str, script: str) -> str:
    result = run_cmd(["multipass", "exec", vm_name, "--", "bash", "-lc", script])
    return result.stdout.strip()


def _write_config(config_path: Path, vm_name: str) -> None:
    write_config(
        config_path,
        {
            "vms": {
                vm_name: {
                    "cpu": 1,
                    "ram": "1G",
                    "disk": "5G",
                    "install": ["nvm"],
                }
            },
            "agents": {
                "qwen_main": {
                    "type": "qwen",
                    "vm": vm_name,
                },
                "cline_main": {
                    "type": "cline",
                    "vm": vm_name,
                },
                "codex_main": {
                    "type": "codex",
                    "vm": vm_name,
                },
            },
        },
    )


def _resolve_two_recent_lts_versions(vm_name: str) -> tuple[str, str]:
    script = r'''
set -eo pipefail
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
mapfile -t versions < <(nvm ls-remote --lts | sed -n 's/^[[:space:]]*\(v[0-9][^[:space:]]*\).*/\1/p')
if [ "${#versions[@]}" -lt 2 ]; then
  echo "Need at least two LTS versions from nvm ls-remote --lts." >&2
  exit 1
fi
latest="${versions[${#versions[@]}-1]}"
previous="${versions[${#versions[@]}-2]}"
printf '%s\n%s\n' "$previous" "$latest"
'''
    result = _vm_bash(vm_name, script).splitlines()
    assert len(result) == 2
    return result[0], result[1]


def _install_agents_across_two_node_versions(vm_name: str, older_version: str, newer_version: str) -> None:
    script = f'''
set -eo pipefail
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm install "{older_version}" >/dev/null
nvm install "{newer_version}" >/dev/null
nvm exec "{older_version}" npm install -g @qwen-code/qwen-code@latest >/dev/null
nvm exec "{newer_version}" npm install -g cline@latest >/dev/null
nvm alias default "{newer_version}" >/dev/null
nvm use --silent default >/dev/null
'''
    _vm_bash(vm_name, script)


def _count_installed_node_versions(vm_name: str) -> int:
    script = r'''
set -eu
export NVM_DIR="$HOME/.nvm"
count=0
for version_dir in "$NVM_DIR"/versions/node/v*; do
  [ -d "$version_dir" ] || continue
  count=$((count + 1))
done
printf '%s\n' "$count"
'''
    return int(_vm_bash(vm_name, script))


def _default_node_version(vm_name: str) -> str:
    script = r'''
set -eo pipefail
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use --silent default >/dev/null
node -v
'''
    return _vm_bash(vm_name, script)


def _assert_agent_works(vm_name: str, binary: str) -> None:
    script = f'''
set -eo pipefail
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use --silent default >/dev/null
{binary} --version
'''
    _vm_bash(vm_name, script)


def _assert_agent_absent(vm_name: str, binary: str) -> None:
    result = run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            (
                'set -eo pipefail; '
                'export NVM_DIR="$HOME/.nvm"; '
                '. "$NVM_DIR/nvm.sh"; '
                'nvm use --silent default >/dev/null; '
                f'command -v {binary}'
            ),
        ],
        check=False,
    )
    assert result.returncode != 0, result.stdout


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    require_host_tools()
    if shutil.which("multipass") is None:
        run_cli(["prepare", "--non-interactive"])
    _skip_if_multipass_unusable()


def test_doctor_merges_scattered_node_agents_into_single_default_version(tmp_path: Path) -> None:
    vm_name = random_vm_name("it-doctor-node")
    config_path = tmp_path / "config.yaml"
    _delete_if_exists(vm_name)
    try:
        _write_config(config_path, vm_name)
        run_cli(["create-vms", "--config", str(config_path), "--non-interactive"])

        older_version, newer_version = _resolve_two_recent_lts_versions(vm_name)
        assert older_version != newer_version

        _install_agents_across_two_node_versions(vm_name, older_version, newer_version)
        assert _count_installed_node_versions(vm_name) == 2

        env = clean_env(
            {
                "AGSEKIT_LANG": "en",
                "TERM": "xterm-256color",
                "PYTHONUNBUFFERED": "1",
                "COLUMNS": "120",
                "LINES": "40",
            }
        )
        child = pexpect.spawn(
            sys.executable,
            [str(REPO_ROOT / "agsekit"), "doctor", "--config", str(config_path)],
            cwd=str(REPO_ROOT),
            env=env,
            encoding="utf-8",
            timeout=120,
        )
        child.expect_exact("Apply fixes now?")
        child.sendline("y")
        child.expect(pexpect.EOF)
        child.close()

        assert child.exitstatus == 0, child.before

        assert _count_installed_node_versions(vm_name) == 1
        assert _default_node_version(vm_name) == newer_version
        _assert_agent_works(vm_name, "qwen")
        _assert_agent_works(vm_name, "cline")
        _assert_agent_absent(vm_name, "codex")
    finally:
        _delete_if_exists(vm_name)
