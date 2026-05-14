from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import pytest

from tests.integration.utils import random_vm_name, require_host_tools, run_cli, run_cmd, write_config


pytestmark = pytest.mark.host_integration


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


def _write_vm_config(
    config_path: Path,
    vm_name: str,
    *,
    install: list[str],
    agent_name: Optional[str] = None,
    agent_type: Optional[str] = None,
) -> None:
    payload = {
        "vms": {
            vm_name: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
                "install": install,
            }
        }
    }
    if agent_name and agent_type:
        payload["agents"] = {
            agent_name: {
                "type": agent_type,
                "vm": vm_name,
            }
        }
    write_config(config_path, payload)


def _resolve_previous_and_current_lts(vm_name: str) -> tuple[str, str]:
    script = r'''
set -eo pipefail
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
mapfile -t versions < <(nvm ls-remote --lts | sed -n 's/^[[:space:]]*\(v[0-9][^[:space:]]*\).*/\1/p')
if [ "${#versions[@]}" -eq 0 ]; then
  echo "No LTS versions were returned by nvm ls-remote --lts." >&2
  exit 1
fi
current="${versions[${#versions[@]}-1]}"
current_major="${current#v}"
current_major="${current_major%%.*}"
previous=""
for ((idx=${#versions[@]}-1; idx>=0; idx--)); do
  candidate="${versions[$idx]}"
  candidate_major="${candidate#v}"
  candidate_major="${candidate_major%%.*}"
  if [ "$candidate_major" != "$current_major" ]; then
    previous="$candidate"
    break
  fi
done
if [ -z "$previous" ]; then
  echo "Failed to resolve the previous Node.js LTS line." >&2
  exit 1
fi
printf '%s\n%s\n' "$previous" "$current"
'''
    result = _vm_bash(vm_name, script).splitlines()
    assert len(result) == 2
    return result[0], result[1]


def _install_node_as_default(vm_name: str, version: str) -> str:
    script = f'''
set -eo pipefail
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm install "{version}" >/dev/null
nvm alias default "{version}" >/dev/null
nvm use --silent default >/dev/null
node -v
'''
    return _vm_bash(vm_name, script)


def _default_node_version(vm_name: str) -> str:
    script = r'''
set -eo pipefail
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use --silent default >/dev/null
node -v
'''
    return _vm_bash(vm_name, script)


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    require_host_tools()
    if shutil.which("multipass") is None:
        run_cli(["prepare", "--non-interactive"])
    _skip_if_multipass_unusable()


def test_create_vms_keeps_existing_previous_lts_node(tmp_path: Path) -> None:
    vm_name = random_vm_name("it-node-lts-create")
    config_path = tmp_path / "config-create-vms.yaml"
    _delete_if_exists(vm_name)
    try:
        _write_vm_config(config_path, vm_name, install=["nvm"])
        run_cli(["create-vms", "--config", str(config_path), "--non-interactive"])

        previous_lts, current_lts = _resolve_previous_and_current_lts(vm_name)
        assert previous_lts != current_lts

        before_version = _install_node_as_default(vm_name, previous_lts)
        assert before_version == previous_lts

        _write_vm_config(config_path, vm_name, install=["nvm", "nodejs"])
        run_cli(["create-vms", "--config", str(config_path), "--non-interactive"])

        after_version = _default_node_version(vm_name)
        assert after_version == previous_lts
    finally:
        _delete_if_exists(vm_name)


def test_install_agents_keeps_existing_previous_lts_node(tmp_path: Path) -> None:
    vm_name = random_vm_name("it-node-lts-agent")
    agent_name = "qwen-main"
    config_path = tmp_path / "config-install-agents.yaml"
    _delete_if_exists(vm_name)
    try:
        _write_vm_config(
            config_path,
            vm_name,
            install=["nvm"],
            agent_name=agent_name,
            agent_type="qwen",
        )
        run_cli(["create-vms", "--config", str(config_path), "--non-interactive"])

        previous_lts, current_lts = _resolve_previous_and_current_lts(vm_name)
        assert previous_lts != current_lts

        before_version = _install_node_as_default(vm_name, previous_lts)
        assert before_version == previous_lts

        run_cli(
            [
                "install-agents",
                agent_name,
                "--config",
                str(config_path),
                "--non-interactive",
            ]
        )

        after_version = _default_node_version(vm_name)
        assert after_version == previous_lts
    finally:
        _delete_if_exists(vm_name)
