from __future__ import annotations

import json
import re
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pytest

from agsekit_cli.agents_modules import DEFAULT_AGENT_VERSIONS, get_agent_class
from tests.integration.utils import random_vm_name, require_host_tools, run_cli, run_cmd, start_cli, wait_for, write_config


pytestmark = pytest.mark.host_integration

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$")
_FAST_AGENT_TYPES = (
    "aider",
    "qwen",
    "forgecode",
    "codex",
    "opencode",
    "claude",
    "cline",
    "codex-glibc-prebuilt",
)


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


def _fetch_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": "agsekit-it"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _parse_semver(version: str) -> Optional[Tuple[int, int, int]]:
    match = _SEMVER_RE.fullmatch(version.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def _sorted_semvers(values: Iterable[str]) -> List[str]:
    valid = [value for value in values if _parse_semver(value) is not None]
    return sorted(valid, key=lambda item: _parse_semver(item) or (0, 0, 0))


def _previous_npm_version(package_name: str, current_version: str) -> str:
    payload = _fetch_json("https://registry.npmjs.org/{name}".format(name=urllib.parse.quote(package_name, safe="@/")))
    versions = payload.get("versions", {}).keys() if isinstance(payload, dict) else []
    older = [version for version in _sorted_semvers(versions) if _parse_semver(version) < _parse_semver(current_version)]
    if not older:
        raise AssertionError("No older npm version found for {name}".format(name=package_name))
    return older[-1]


def _previous_pypi_version(package_name: str, current_version: str) -> str:
    payload = _fetch_json("https://pypi.org/pypi/{name}/json".format(name=package_name))
    releases = payload.get("releases", {}).keys() if isinstance(payload, dict) else []
    older = [version for version in _sorted_semvers(releases) if _parse_semver(version) < _parse_semver(current_version)]
    if not older:
        raise AssertionError("No older PyPI version found for {name}".format(name=package_name))
    return older[-1]


def _previous_github_release_version(repo: str, current_version: str, *, prefix: str) -> str:
    payload = _fetch_json("https://api.github.com/repos/{repo}/releases?per_page=100".format(repo=repo))
    versions: List[str] = []
    for release in payload if isinstance(payload, list) else []:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        tag_name = release.get("tag_name")
        if not isinstance(tag_name, str) or not tag_name.startswith(prefix):
            continue
        normalized = tag_name[len(prefix):]
        if _parse_semver(normalized) is not None:
            versions.append(normalized)
    older = [version for version in _sorted_semvers(versions) if _parse_semver(version) < _parse_semver(current_version)]
    if not older:
        raise AssertionError("No older GitHub release version found for {repo}".format(repo=repo))
    return older[-1]


def _alternate_versions() -> Dict[str, str]:
    return {
        "aider": _previous_pypi_version("aider-chat", DEFAULT_AGENT_VERSIONS["aider"]),
        "qwen": _previous_npm_version("@qwen-code/qwen-code", DEFAULT_AGENT_VERSIONS["qwen"]),
        "forgecode": _previous_github_release_version("tailcallhq/forgecode", DEFAULT_AGENT_VERSIONS["forgecode"], prefix="v"),
        "codex": _previous_npm_version("@openai/codex", DEFAULT_AGENT_VERSIONS["codex"]),
        "opencode": _previous_npm_version("opencode-ai", DEFAULT_AGENT_VERSIONS["opencode"]),
        "claude": _previous_npm_version("@anthropic-ai/claude-code", DEFAULT_AGENT_VERSIONS["claude"]),
        "cline": _previous_npm_version("cline", DEFAULT_AGENT_VERSIONS["cline"]),
        "codex-glibc-prebuilt": _previous_github_release_version(
            "MihanEntalpo/agent-safety-kit",
            DEFAULT_AGENT_VERSIONS["codex-glibc-prebuilt"],
            prefix="codex-glibc-rust-v",
        ),
        "codex-glibc": _previous_github_release_version(
            "openai/codex",
            DEFAULT_AGENT_VERSIONS["codex-glibc"],
            prefix="rust-v",
        ),
    }


def _instance_exists(name: str) -> bool:
    result = run_cmd(["multipass", "list", "--format", "json"])
    return f'"name":"{name}"' in result.stdout.replace(" ", "")


def _delete_if_exists(name: str) -> None:
    if not _instance_exists(name):
        return
    run_cmd(["multipass", "delete", name], check=False)
    run_cmd(["multipass", "purge"], check=False)


def _launch_vm(name: str) -> None:
    command = ["multipass", "launch", "--name", name, "--cpus", "2", "--memory", "4G", "--disk", "20G"]
    for attempt in range(1, 4):
        result = run_cmd(command, check=False)
        if result.returncode == 0:
            return
        stderr = (result.stderr or "").lower()
        if attempt < 3 and "remote" in stderr and "unknown or unreachable" in stderr:
            run_cmd(["multipass", "find"], check=False)
            time.sleep(attempt)
            continue
        raise AssertionError(result.stderr or result.stdout or "multipass launch failed")


def _write_agents_config(
    config_path: Path,
    vm_name: str,
    *,
    versions: Optional[Dict[str, str]] = None,
    include_codex_glibc: bool = False,
) -> None:
    payload = {
        "vms": {
            vm_name: {
                "cpu": 2,
                "ram": "4G",
                "disk": "20G",
            }
        },
        "agents": {},
    }
    agent_types = list(_FAST_AGENT_TYPES)
    if include_codex_glibc:
        agent_types.append("codex-glibc")
    for agent_type in agent_types:
        entry = {
            "type": agent_type,
            "vm": vm_name,
        }
        if versions and agent_type in versions:
            entry["version"] = versions[agent_type]
        else:
            entry["version"] = "stable"
        payload["agents"][agent_type] = entry
    write_config(config_path, payload)


def _installed_agent_version(vm_name: str, agent_type: str) -> str:
    agent_cls = get_agent_class(agent_type)
    command = ["multipass", "exec", vm_name, "--", "bash", "-lc", agent_cls.build_version_command()]
    result = run_cmd(command)
    version = agent_cls.extract_version("\n".join(part for part in (result.stdout, result.stderr) if part).strip())
    if version is None:
        raise AssertionError("Could not parse installed version for {agent_type}".format(agent_type=agent_type))
    return version


def _cloned_codex_tag(vm_name: str) -> str:
    result = run_cmd(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            "git -C /tmp/codex-src/codex describe --tags --exact-match",
        ],
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    require_host_tools()
    if shutil.which("multipass") is None:
        run_cli(["prepare", "--non-interactive"])
    _skip_if_multipass_unusable()


def test_install_agents_pins_default_versions_and_reinstalls_requested_ones(tmp_path: Path) -> None:
    vm_name = random_vm_name("it-agent-versions")
    config_path = tmp_path / "config.yaml"
    _delete_if_exists(vm_name)
    try:
        _write_agents_config(config_path, vm_name)
        _launch_vm(vm_name)

        run_cli(["install-agents", "--all-agents", "--config", str(config_path), "--non-interactive"])

        for agent_type in _FAST_AGENT_TYPES:
            assert _installed_agent_version(vm_name, agent_type) == DEFAULT_AGENT_VERSIONS[agent_type]

        requested_versions = _alternate_versions()
        _write_agents_config(config_path, vm_name, versions=requested_versions)
        run_cli(["install-agents", "--all-agents", "--config", str(config_path), "--non-interactive"])

        for agent_type in _FAST_AGENT_TYPES:
            assert _installed_agent_version(vm_name, agent_type) == requested_versions[agent_type]
    finally:
        _delete_if_exists(vm_name)


def test_codex_glibc_clone_uses_requested_tag_without_waiting_for_full_build(tmp_path: Path) -> None:
    vm_name = random_vm_name("it-codex-glibc-version")
    config_path = tmp_path / "config-codex-glibc.yaml"
    requested_version = _alternate_versions()["codex-glibc"]
    _delete_if_exists(vm_name)
    try:
        _write_agents_config(
            config_path,
            vm_name,
            versions={"codex-glibc": requested_version},
            include_codex_glibc=True,
        )
        _launch_vm(vm_name)

        process = start_cli(
            [
                "install-agents",
                "codex-glibc",
                "--config",
                str(config_path),
                "--non-interactive",
            ]
        )
        try:
            wait_for(
                lambda: _cloned_codex_tag(vm_name) == "rust-v{version}".format(version=requested_version),
                timeout=180.0,
                message="codex-glibc repository is cloned on the requested tag",
                interval=2.0,
            )
        finally:
            process.terminate()
            process.wait(timeout=30)
    finally:
        _delete_if_exists(vm_name)
