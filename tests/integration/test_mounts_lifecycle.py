from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import pytest
import yaml


pytestmark = pytest.mark.host_integration

REPO_ROOT = Path(__file__).resolve().parents[2]


def _clean_env(overrides: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "PROXYCHAINS_CONF_FILE"):
        env.pop(key, None)
    if overrides:
        env.update(overrides)
    return env


def _run(
    command: list[str],
    check: bool = True,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    effective_env = _clean_env(env)
    return subprocess.run(command, check=check, text=True, capture_output=True, cwd=cwd, env=effective_env)


def _run_cli(args: list[str], check: bool = True, cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
    env = _clean_env()
    env["AGSEKIT_LANG"] = "en"
    return _run([sys.executable, str(REPO_ROOT / "agsekit"), *args], check=check, cwd=cwd or REPO_ROOT, env=env)


def _require_host_tools() -> None:
    if shutil.which("apt-get") is None:
        pytest.skip("apt-get is required for host integration tests")
    if os.geteuid() != 0 and shutil.which("sudo") is None:
        pytest.skip("sudo or root access is required for host integration tests")
    if os.geteuid() != 0:
        sudo_check = subprocess.run(
            ["sudo", "-n", "true"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if sudo_check.returncode != 0:
            pytest.skip("passwordless sudo is required for host integration tests")


def _skip_if_multipass_unusable(result: subprocess.CompletedProcess[str]) -> None:
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    details = "\n".join(part for part in (stderr, stdout) if part)
    markers = (
        "execv failed",
        "snap-confine is packaged without necessary permissions",
    )
    if any(marker in details for marker in markers):
        pytest.skip(f"multipass is installed but not executable in this environment: {details}")


def _random_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _instance_exists(name: str) -> bool:
    result = _run(["multipass", "list", "--format", "json"], check=True)
    payload = json.loads(result.stdout)
    for entry in payload.get("list", []):
        if entry.get("name") == name:
            return True
    return False


def _delete_if_exists(name: str) -> None:
    if not _instance_exists(name):
        return
    _run(["multipass", "delete", name], check=False)
    _run(["multipass", "purge"], check=False)


def _launch_vm(name: str) -> None:
    launch_cmd = ["multipass", "launch", "--name", name, "--cpus", "1", "--memory", "1G", "--disk", "5G"]
    for attempt in range(1, 4):
        result = _run(launch_cmd, check=False)
        if result.returncode == 0:
            return
        stderr = (result.stderr or "").lower()
        if attempt < 3 and "remote" in stderr and "unknown or unreachable" in stderr:
            _run(["multipass", "find"], check=False)
            time.sleep(attempt)
            continue
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "multipass launch failed")


def _write_config(config_path: Path, vm_name: str, mounts: list[dict[str, object]]) -> None:
    payload = {
        "vms": {
            vm_name: {
                "cpu": 1,
                "ram": "1G",
                "disk": "5G",
            }
        },
        "mounts": mounts,
    }
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _marker_exists_in_vm(vm_name: str, target: Path, marker_name: str) -> bool:
    result = _run(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-lc",
            f"test -f {target}/{marker_name}",
        ],
        check=False,
    )
    return result.returncode == 0


def _wait_for_marker(vm_name: str, target: Path, marker_name: str, expected: bool, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _marker_exists_in_vm(vm_name, target, marker_name) is expected:
            return
        time.sleep(0.25)
    state = "present" if expected else "absent"
    raise AssertionError(f"Expected marker to become {state}: {target}/{marker_name}")


@pytest.fixture(scope="module", autouse=True)
def ensure_multipass_ready() -> None:
    _require_host_tools()
    if shutil.which("multipass") is None:
        _run_cli(["prepare", "--non-interactive"], check=True)
    check = _run(["multipass", "version"], check=False)
    _skip_if_multipass_unusable(check)
    if check.returncode != 0:
        pytest.skip(check.stderr or check.stdout or "multipass is not ready")


@pytest.fixture(scope="module")
def mount_test_vm() -> str:
    vm_name = _random_name("it-mount-vm")
    _delete_if_exists(vm_name)
    _launch_vm(vm_name)
    try:
        yield vm_name
    finally:
        _delete_if_exists(vm_name)


@pytest.fixture(scope="module")
def host_mount_root() -> Path:
    root = Path.home() / ".agsekit-it-mounts" / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_mount_single_source_is_visible_inside_vm(mount_test_vm: str, host_mount_root: Path, tmp_path: Path) -> None:
    source = host_mount_root / "source-one"
    source.mkdir()
    marker_name = "marker-one.txt"
    (source / marker_name).write_text("hello", encoding="utf-8")
    target = Path("/home/ubuntu") / _random_name("it-target-one")
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        mount_test_vm,
        [{"source": str(source), "target": str(target), "vm": mount_test_vm}],
    )

    result = _run_cli(["mount", str(source), "--config", str(config_path), "--non-interactive", "--debug"], check=True)

    assert result.returncode == 0
    _wait_for_marker(mount_test_vm, target, marker_name, expected=True)


def test_mount_all_mounts_every_entry(mount_test_vm: str, host_mount_root: Path, tmp_path: Path) -> None:
    source_one = host_mount_root / "source-all-one"
    source_two = host_mount_root / "source-all-two"
    source_one.mkdir()
    source_two.mkdir()
    marker_one = "one.txt"
    marker_two = "two.txt"
    (source_one / marker_one).write_text("one", encoding="utf-8")
    (source_two / marker_two).write_text("two", encoding="utf-8")
    target_one = Path("/home/ubuntu") / _random_name("it-target-all-one")
    target_two = Path("/home/ubuntu") / _random_name("it-target-all-two")
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        mount_test_vm,
        [
            {"source": str(source_one), "target": str(target_one), "vm": mount_test_vm},
            {"source": str(source_two), "target": str(target_two), "vm": mount_test_vm},
        ],
    )

    result = _run_cli(["mount", "--all", "--config", str(config_path), "--non-interactive", "--debug"], check=True)

    assert result.returncode == 0
    _wait_for_marker(mount_test_vm, target_one, marker_one, expected=True)
    _wait_for_marker(mount_test_vm, target_two, marker_two, expected=True)


def test_umount_removes_mount_from_vm(mount_test_vm: str, host_mount_root: Path, tmp_path: Path) -> None:
    source = host_mount_root / "source-umount"
    source.mkdir()
    marker_name = "marker-umount.txt"
    (source / marker_name).write_text("bye", encoding="utf-8")
    target = Path("/home/ubuntu") / _random_name("it-target-umount")
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        mount_test_vm,
        [{"source": str(source), "target": str(target), "vm": mount_test_vm}],
    )

    _run_cli(["mount", str(source), "--config", str(config_path), "--non-interactive"], check=True)
    _wait_for_marker(mount_test_vm, target, marker_name, expected=True)

    result = _run_cli(["umount", str(source), "--config", str(config_path), "--non-interactive", "--debug"], check=True)

    assert result.returncode == 0
    _wait_for_marker(mount_test_vm, target, marker_name, expected=False)


def test_addmount_with_mount_flag_updates_yaml_and_mounts(mount_test_vm: str, host_mount_root: Path, tmp_path: Path) -> None:
    source = host_mount_root / "source-addmount"
    source.mkdir()
    marker_name = "marker-addmount.txt"
    (source / marker_name).write_text("add", encoding="utf-8")
    target = Path("/home/ubuntu") / _random_name("it-target-addmount")
    backup = host_mount_root / "backup-addmount"
    backup.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, mount_test_vm, [])

    result = _run_cli(
        [
            "addmount",
            str(source),
            str(target),
            str(backup),
            "7",
            "--max-backups",
            "11",
            "--backup-clean-method",
            "thin",
            "--mount",
            "-y",
            "--config",
            str(config_path),
            "--non-interactive",
            "--debug",
        ],
        check=True,
    )

    assert result.returncode == 0
    updated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    mounts = updated.get("mounts") or []
    assert len(mounts) == 1
    entry = mounts[0]
    assert Path(entry["source"]).resolve() == source.resolve()
    assert Path(entry["target"]).resolve() == target.resolve()
    assert Path(entry["backup"]).resolve() == backup.resolve()
    assert int(entry["interval"]) == 7
    assert int(entry["max_backups"]) == 11
    assert str(entry["backup_clean_method"]) == "thin"
    _wait_for_marker(mount_test_vm, target, marker_name, expected=True)


def test_removemount_unmounts_and_deletes_yaml_entry(mount_test_vm: str, host_mount_root: Path, tmp_path: Path) -> None:
    source = host_mount_root / "source-removemount"
    source.mkdir()
    marker_name = "marker-removemount.txt"
    (source / marker_name).write_text("remove", encoding="utf-8")
    target = Path("/home/ubuntu") / _random_name("it-target-removemount")
    backup = host_mount_root / "backup-removemount"
    backup.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        mount_test_vm,
        [
            {
                "source": str(source),
                "target": str(target),
                "backup": str(backup),
                "interval": 5,
                "max_backups": 100,
                "backup_clean_method": "thin",
                "vm": mount_test_vm,
            }
        ],
    )

    _run_cli(["mount", str(source), "--config", str(config_path), "--non-interactive"], check=True)
    _wait_for_marker(mount_test_vm, target, marker_name, expected=True)

    result = _run_cli(
        [
            "removemount",
            str(source),
            "--config",
            str(config_path),
            "-y",
            "--non-interactive",
            "--debug",
        ],
        check=True,
    )

    assert result.returncode == 0
    updated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert not (updated.get("mounts") or [])
    _wait_for_marker(mount_test_vm, target, marker_name, expected=False)


def test_mount_and_umount_resolve_relative_nested_path(
    mount_test_vm: str, host_mount_root: Path, tmp_path: Path
) -> None:
    source = host_mount_root / "source-relative"
    nested = source / "nested" / "inner"
    nested.mkdir(parents=True)
    marker_name = "marker-relative.txt"
    (source / marker_name).write_text("relative", encoding="utf-8")
    sibling = host_mount_root / "sibling"
    sibling.mkdir()
    target = Path("/home/ubuntu") / _random_name("it-target-relative")
    backup = host_mount_root / "backup-relative"
    backup.mkdir()
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        mount_test_vm,
        [
            {
                "source": str(source),
                "target": str(target),
                "backup": str(backup),
                "interval": 5,
                "max_backups": 100,
                "backup_clean_method": "thin",
                "vm": mount_test_vm,
            }
        ],
    )

    relative_mount_arg = str(Path("..") / source.name / "nested")
    relative_umount_arg = str(Path("..") / source.name / "nested" / "inner")

    mount_result = _run_cli(
        [
            "mount",
            relative_mount_arg,
            "--config",
            str(config_path),
            "--non-interactive",
            "--debug",
        ],
        check=True,
        cwd=sibling,
    )
    assert mount_result.returncode == 0
    _wait_for_marker(mount_test_vm, target, marker_name, expected=True)

    umount_result = _run_cli(
        [
            "umount",
            relative_umount_arg,
            "--config",
            str(config_path),
            "--non-interactive",
            "--debug",
        ],
        check=True,
        cwd=sibling,
    )
    assert umount_result.returncode == 0
    _wait_for_marker(mount_test_vm, target, marker_name, expected=False)
