from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pytest
import yaml

from agsekit_cli.agents_modules import AGENT_RUNTIME_BINARIES, get_agent_class
from tests.integration.utils import (
    REPO_ROOT,
    random_vm_name,
    require_host_tools,
    run_cli,
    run_cmd,
    write_config,
)


pytestmark = pytest.mark.host_integration


AgentCase = Tuple[str, str, str, str, str]


def _agent_cases(prefix: str) -> List[AgentCase]:
    cases: List[AgentCase] = []
    for agent_type, runtime_binary in sorted(AGENT_RUNTIME_BINARIES.items()):
        agent_cls = get_agent_class(agent_type)
        config_env_name = agent_cls.config_dir_env_name
        config_rel_path = agent_cls.config_dir_relative_path
        legacy_paths = agent_cls.migration_allow_paths()
        legacy_rel_path = legacy_paths[0] if legacy_paths else ""
        for suffix in ("a", "b"):
            agent_name = f"{agent_type}-{prefix}-{suffix}"
            cases.append((agent_name, agent_type, runtime_binary, config_env_name, config_rel_path or legacy_rel_path))
    return cases


def _write_agent_home_config(config_path: Path, vm_name: str, source: Path, cases: Iterable[AgentCase]) -> None:
    agents: Dict[str, object] = {}
    for agent_name, agent_type, _runtime_binary, config_env_name, config_rel_path in cases:
        agent_env = {
            "AGSEKIT_IT_AGENT_NAME": agent_name,
            "AGSEKIT_IT_CONFIG_ENV_NAME": config_env_name,
            "AGSEKIT_IT_CONFIG_REL_PATH": config_rel_path,
        }
        agents[agent_name] = {
            "type": agent_type,
            "vm": vm_name,
            "env": agent_env,
        }

    payload = {
        "vms": {
            vm_name: {
                "cpu": 1,
                "ram": "1G",
                "disk": "6G",
            }
        },
        "mounts": [
            {
                "source": str(source),
                "backup": str(source.parent / "backups"),
                "interval": 1,
                "max_backups": 3,
                "backup_clean_method": "tail",
                "first_backup": False,
                "vm": vm_name,
            }
        ],
        "agents": agents,
    }
    write_config(config_path, payload)


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    require_host_tools()
    run_cli(["prepare", "--non-interactive"], check=True)
    check = run_cmd(["multipass", "version"], check=False)
    if check.returncode != 0:
        pytest.skip(check.stderr or check.stdout or "multipass is not ready")


@pytest.fixture(scope="module")
def agent_home_vm(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("agent-home-migration")
    base_dir = REPO_ROOT / f".tmp-agent-home-{random_vm_name('data')}"
    source = base_dir / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "file.txt").write_text("content", encoding="utf-8")

    vm_name = random_vm_name("it-agent-home")
    config_path = tmp_path / "config.yaml"
    _write_agent_home_config(config_path, vm_name, source, _agent_cases("fresh"))

    run_cli(["create-vm", vm_name, "--config", str(config_path), "--non-interactive"], check=True)
    _install_dummy_agent_binaries(vm_name)

    try:
        yield {
            "vm_name": vm_name,
            "source": source,
            "config_path": config_path,
            "tmp_path": tmp_path,
            "base_dir": base_dir,
        }
    finally:
        run_cmd(["multipass", "delete", vm_name], check=False)
        run_cmd(["multipass", "purge"], check=False)
        if base_dir.exists():
            shutil.rmtree(base_dir)


def _install_dummy_agent_binaries(vm_name: str) -> None:
    script = r"""#!/usr/bin/env bash
set -euo pipefail

agent_name="${AGSEKIT_IT_AGENT_NAME:?}"
expected_home="/home/ubuntu/.agent-homes/${agent_name}"
test "${HOME}" = "${expected_home}"
test "${XDG_CONFIG_HOME}" = "${expected_home}/.config"
test "${XDG_DATA_HOME}" = "${expected_home}/.local/share"
test "${XDG_CACHE_HOME}" = "${expected_home}/.cache"
test "${XDG_STATE_HOME}" = "${expected_home}/.local/state"

mkdir -p "${HOME}"
printf '%s\n' "${agent_name}" > "${HOME}/agent-home-used"

config_env_name="${AGSEKIT_IT_CONFIG_ENV_NAME:-}"
config_rel_path="${AGSEKIT_IT_CONFIG_REL_PATH:-}"
if [[ -n "${config_env_name}" ]]; then
  config_dir="${!config_env_name:-}"
  test "${config_dir}" = "${expected_home}/${config_rel_path}"
  mkdir -p "${config_dir}"
  printf '%s\n' "${agent_name}" > "${config_dir}/config-env-used"
fi

legacy_rel_path="${AGSEKIT_IT_EXPECT_LEGACY_REL_PATH:-}"
if [[ -n "${legacy_rel_path}" ]]; then
  legacy_target="${HOME}/${legacy_rel_path}"
  if [[ -d "${legacy_target}" ]]; then
    test -f "${legacy_target}/legacy.txt"
  else
    test -f "${legacy_target}"
    grep -q 'legacy-data' "${legacy_target}"
  fi
fi
"""
    binaries = sorted(set(AGENT_RUNTIME_BINARIES.values()))
    quoted_binaries = " ".join(json.dumps(binary) for binary in binaries)
    command = (
        "cat > /tmp/agsekit-it-agent <<'EOF'\n"
        f"{script}\n"
        "EOF\n"
        "sudo chmod +x /tmp/agsekit-it-agent\n"
        f"for binary in {quoted_binaries}; do sudo cp /tmp/agsekit-it-agent \"/usr/local/bin/${{binary}}\"; done"
    )
    run_cmd(["multipass", "exec", vm_name, "--", "bash", "-lc", command], check=True)


def _run_agent(config_path: Path, source: Path, agent_name: str) -> None:
    result = run_cli(
        [
            "run",
            "--config",
            str(config_path),
            "--workdir",
            str(source),
            "--disable-backups",
            "--auto-mount",
            "--non-interactive",
            agent_name,
        ],
        check=False,
    )
    assert result.returncode == 0, f"agent={agent_name}\nstdout={result.stdout}\nstderr={result.stderr}"


def _assert_agent_home_used(vm_name: str, agent_name: str, config_env_name: str, config_rel_path: str) -> None:
    checks = [
        f"test -f /home/ubuntu/.agent-homes/{agent_name}/agent-home-used",
        f"grep -q {agent_name!r} /home/ubuntu/.agent-homes/{agent_name}/agent-home-used",
    ]
    if config_env_name:
        checks.extend(
            [
                f"test -f /home/ubuntu/.agent-homes/{agent_name}/{config_rel_path}/config-env-used",
                f"grep -q {agent_name!r} /home/ubuntu/.agent-homes/{agent_name}/{config_rel_path}/config-env-used",
            ]
        )
    command = " && ".join(checks)
    run_cmd(["multipass", "exec", vm_name, "--", "bash", "-lc", command], check=True)


def _legacy_path_is_file(relative_path: str) -> bool:
    return relative_path.endswith((".json", ".yaml", ".yml", ".toml"))


def _write_legacy_home_paths(vm_name: str) -> None:
    commands: List[str] = []
    for agent_type in sorted(AGENT_RUNTIME_BINARIES):
        allow_paths = get_agent_class(agent_type).migration_allow_paths()
        for relative_path in allow_paths:
            target = f"/home/ubuntu/{relative_path}"
            if _legacy_path_is_file(relative_path):
                commands.append(f"mkdir -p {json.dumps(str(Path(target).parent))}")
                commands.append(f"printf 'legacy-data:{agent_type}\\n' > {json.dumps(target)}")
            else:
                commands.append(f"mkdir -p {json.dumps(target)}")
                commands.append(f"printf 'legacy-data:{agent_type}\\n' > {json.dumps(target + '/legacy.txt')}")
    run_cmd(["multipass", "exec", vm_name, "--", "bash", "-lc", " && ".join(commands)], check=True)


def _assert_legacy_paths_copied(vm_name: str, agent_name: str, legacy_paths: Iterable[str]) -> None:
    checks: List[str] = []
    for relative_path in legacy_paths:
        target = f"/home/ubuntu/.agent-homes/{agent_name}/{relative_path}"
        if _legacy_path_is_file(relative_path):
            checks.append(f"test -f {json.dumps(target)}")
            checks.append(f"grep -q legacy-data {json.dumps(target)}")
        else:
            marker = f"{target}/legacy.txt"
            checks.append(f"test -f {json.dumps(marker)}")
            checks.append(f"grep -q legacy-data {json.dumps(marker)}")
    run_cmd(["multipass", "exec", vm_name, "--", "bash", "-lc", " && ".join(checks)], check=True)


def _install_legacy_run_wrapper_without_allow_home_path(vm_name: str) -> None:
    script = r"""#!/usr/bin/env bash
set -euo pipefail

while [[ $# -gt 0 ]]; do
  case "$1" in
    --allow-home-path)
      echo "unknown option: --allow-home-path" >&2
      exit 2
      ;;
    --)
      shift
      break
      ;;
    *)
      shift
      ;;
  esac
done

exec "$@"
"""
    command = (
        "cat > /tmp/agsekit-legacy-run-agent.sh <<'EOF'\n"
        f"{script}\n"
        "EOF\n"
        "sudo mv /tmp/agsekit-legacy-run-agent.sh /usr/bin/agsekit-run_agent.sh && "
        "sudo chmod +x /usr/bin/agsekit-run_agent.sh"
    )
    run_cmd(["multipass", "exec", vm_name, "--", "bash", "-lc", command], check=True)


def test_all_agent_profiles_create_and_use_separate_per_agent_homes(agent_home_vm) -> None:
    vm_name = agent_home_vm["vm_name"]
    source = agent_home_vm["source"]
    config_path = agent_home_vm["config_path"]
    cases = _agent_cases("fresh")

    for agent_name, _agent_type, _runtime_binary, _config_env_name, _config_rel_path in cases:
        _run_agent(config_path, source, agent_name)

    for agent_name, _agent_type, _runtime_binary, config_env_name, config_rel_path in cases:
        _assert_agent_home_used(vm_name, agent_name, config_env_name, config_rel_path)


def test_all_agent_profiles_bootstrap_missing_per_agent_homes_from_legacy_home(agent_home_vm) -> None:
    vm_name = agent_home_vm["vm_name"]
    source = agent_home_vm["source"]
    tmp_path = agent_home_vm["tmp_path"]
    cases = _agent_cases("migrate")
    config_path = tmp_path / "config-migrate.yaml"
    _write_agent_home_config(config_path, vm_name, source, cases)
    _write_legacy_home_paths(vm_name)

    for agent_name, agent_type, _runtime_binary, _config_env_name, _config_rel_path in cases:
        legacy_paths = get_agent_class(agent_type).migration_allow_paths()
        assert legacy_paths
        agent_env = {
            "AGSEKIT_IT_EXPECT_LEGACY_REL_PATH": legacy_paths[0],
        }
        # Patch only this agent's env in the config before its run so the dummy binary
        # verifies that the copied legacy path is visible inside its per-agent home.
        config_payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config_payload["agents"][agent_name]["env"].update(agent_env)
        write_config(config_path, config_payload)
        _run_agent(config_path, source, agent_name)

    for agent_name, agent_type, _runtime_binary, config_env_name, config_rel_path in cases:
        _assert_agent_home_used(vm_name, agent_name, config_env_name, config_rel_path)
        _assert_legacy_paths_copied(vm_name, agent_name, get_agent_class(agent_type).migration_allow_paths())


def test_run_stops_and_suggests_create_vms_when_vm_wrapper_is_outdated(agent_home_vm) -> None:
    vm_name = agent_home_vm["vm_name"]
    source = agent_home_vm["source"]
    config_path = agent_home_vm["config_path"]

    _install_legacy_run_wrapper_without_allow_home_path(vm_name)
    try:
        result = run_cli(
            [
                "run",
                "--config",
                str(config_path),
                "--workdir",
                str(source),
                "--disable-backups",
                "--auto-mount",
                "--non-interactive",
                "qwen-fresh-a",
            ],
            check=False,
        )

        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        assert result.returncode != 0, output
        assert "outdated" in output
        assert "agsekit create-vms" in output
        assert f"create-vm {vm_name}" not in output
    finally:
        run_cli(["create-vm", vm_name, "--config", str(config_path), "--non-interactive"], check=True)
