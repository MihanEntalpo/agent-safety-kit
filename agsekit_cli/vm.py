from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml

from .config import ConfigError, PortForwardingRule, VmConfig, load_config, load_vms_config
from .i18n import tr

SIZE_MAP: Dict[str, int] = {
    "": 1,
    "B": 1,
    "K": 1024,
    "KB": 1024,
    "KI": 1024,
    "KIB": 1024,
    "M": 1024 ** 2,
    "MB": 1024 ** 2,
    "MI": 1024 ** 2,
    "MIB": 1024 ** 2,
    "G": 1024 ** 3,
    "GB": 1024 ** 3,
    "GI": 1024 ** 3,
    "GIB": 1024 ** 3,
    "T": 1024 ** 4,
    "TB": 1024 ** 4,
    "TI": 1024 ** 4,
    "TIB": 1024 ** 4,
}


class MultipassError(RuntimeError):
    """Raised when multipass operations fail."""


def to_bytes(value: Optional[object]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    match = re.match(r"^(\d+(?:\.\d+)?)([KMGTP]?I?B?)?$", text, re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "").upper()
    factor = SIZE_MAP.get(unit)
    if factor is None:
        return None
    return int(number * factor)


def load_existing_entry(raw: str, name: str) -> Optional[Dict[str, object]]:
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    for item in data.get("list", []):
        if item.get("name") == name:
            return item
    return None


def compare_vm(raw_info: str, name: str, expected_cpus: str, expected_mem_raw: str, expected_disk_raw: str) -> str:
    entry = load_existing_entry(raw_info, name)
    if entry is None:
        return "absent"

    current_cpus = entry.get("cpus")
    current_mem = to_bytes(entry.get("mem") or entry.get("memory") or entry.get("memory_total") or entry.get("ram"))
    current_disk = to_bytes(entry.get("disk") or entry.get("disk_total") or entry.get("disk_space"))

    expected_mem = to_bytes(expected_mem_raw)
    expected_disk = to_bytes(expected_disk_raw)

    mismatches: List[str] = []
    if str(current_cpus) != str(expected_cpus):
        mismatches.append("cpus")
    if current_mem is not None and expected_mem is not None and current_mem != expected_mem:
        mismatches.append("memory")
    if current_disk is not None and expected_disk is not None and current_disk != expected_disk:
        mismatches.append("disk")

    if mismatches:
        return f"mismatch {';'.join(mismatches)}"
    return "match"


def ensure_multipass_available() -> None:
    if shutil.which("multipass") is None:
        raise MultipassError(tr("vm.multipass_missing"))


def fetch_existing_info() -> str:
    result = subprocess.run([
        "multipass",
        "list",
        "--format",
        "json",
    ], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise MultipassError(result.stderr.strip() or tr("vm.list_failed"))
    return result.stdout


def _system_cpu_count() -> int:
    cpu_count = os.cpu_count()
    if cpu_count is None:
        raise MultipassError(tr("vm.cpu_count_failed"))
    return cpu_count


def _system_memory_bytes() -> int:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")  # type: ignore[arg-type]
        page_count = os.sysconf("SC_PHYS_PAGES")  # type: ignore[arg-type]
        return int(page_size) * int(page_count)
    except (AttributeError, ValueError, OSError):
        raise MultipassError(tr("vm.memory_total_failed"))


def _sum_existing_allocations(raw_info: str) -> tuple[int, int]:
    allocated_cpus = 0
    allocated_mem = 0

    try:
        data = json.loads(raw_info)
    except json.JSONDecodeError:
        return 0, 0

    for item in data.get("list", []):
        cpus = item.get("cpus")
        mem = to_bytes(item.get("mem") or item.get("memory") or item.get("memory_total") or item.get("ram"))
        if cpus is not None:
            try:
                allocated_cpus += int(cpus)
            except (TypeError, ValueError):
                continue
        if mem is not None:
            allocated_mem += mem

    return allocated_cpus, allocated_mem


def _planned_resources(vms: Iterable[VmConfig]) -> tuple[int, int]:
    cpus = 0
    mem = 0
    for vm in vms:
        cpus += vm.cpu
        mem_bytes = to_bytes(vm.ram)
        if mem_bytes is None:
            raise ConfigError(tr("vm.memory_parse_failed", vm_name=vm.name, ram=vm.ram))
        mem += mem_bytes
    return cpus, mem


def ensure_resources_available(existing_info: str, planned: Iterable[VmConfig]) -> None:
    planned_cpus, planned_mem = _planned_resources(planned)
    existing_cpus, existing_mem = _sum_existing_allocations(existing_info)

    total_cpus = _system_cpu_count()
    total_mem = _system_memory_bytes()

    remaining_cpus = total_cpus - existing_cpus - planned_cpus
    remaining_mem = total_mem - existing_mem - planned_mem

    if remaining_cpus < 1 or remaining_mem < 1024 ** 3:
        raise MultipassError(tr("vm.insufficient_resources"))


def _format_mismatch_details(details: str) -> str:
    if not details:
        return ""
    mapping = {
        "cpus": tr("vm.mismatch_cpus"),
        "memory": tr("vm.mismatch_memory"),
        "disk": tr("vm.mismatch_disk"),
    }
    items = []
    for chunk in details.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        items.append(mapping.get(chunk, chunk))
    return ", ".join(items)


def _dump_cloud_init(data: Dict[str, object]) -> Optional[Path]:
    if not data:
        return None

    temp = tempfile.NamedTemporaryFile(delete=False, suffix="-cloudinit.yaml")
    try:
        yaml.safe_dump(data, temp)
        temp.flush()
        return Path(temp.name)
    finally:
        temp.close()


def _build_launch_command(vm_config: VmConfig, cloud_init_path: Optional[Path]) -> List[str]:
    command = [
        "multipass",
        "launch",
        "--name",
        vm_config.name,
        "--cpus",
        str(vm_config.cpu),
        "--memory",
        vm_config.ram,
        "--disk",
        vm_config.disk,
    ]

    if cloud_init_path:
        command.extend(["--cloud-init", str(cloud_init_path)])

    return command


def do_launch(vm_config: VmConfig, existing_info: str) -> str:
    comparison_result = compare_vm(
        existing_info,
        vm_config.name,
        str(vm_config.cpu),
        vm_config.ram,
        vm_config.disk,
    )

    status, _, details = comparison_result.partition(" ")
    if status == "mismatch":
        readable = _format_mismatch_details(details)
        raise MultipassError(tr("vm.mismatch_not_supported", vm_name=vm_config.name, details=readable))
    if status == "match":
        return tr("vm.already_matches", vm_name=vm_config.name)
    if status != "absent":
        raise MultipassError(tr("vm.status_unknown", vm_name=vm_config.name, response=comparison_result))

    cloud_init_path = _dump_cloud_init(vm_config.cloud_init)
    try:
        launch_cmd = _build_launch_command(vm_config, cloud_init_path)
        launch_result = subprocess.run(launch_cmd, check=False, capture_output=True, text=True)
    finally:
        if cloud_init_path:
            try:
                cloud_init_path.unlink()
            except OSError:
                pass

    if launch_result.returncode != 0:
        raise MultipassError(launch_result.stderr.strip() or tr("vm.create_failed"))
    return tr("vm.created", vm_name=vm_config.name)


def build_port_forwarding_args(rules: Iterable[PortForwardingRule]) -> List[str]:
    args: List[str] = []
    for rule in rules:
        if rule.type == "local":
            args.extend(["-L", f"{rule.host_addr}:{rule.vm_addr}"])
        elif rule.type == "remote":
            args.extend(["-R", f"{rule.vm_addr}:{rule.host_addr}"])
        elif rule.type == "socks5":
            args.extend(["-D", rule.vm_addr])
    return args


PROXYCHAINS_RUNNER_REMOTE = "/tmp/agsekit-run_with_proxychains.sh"
PROXYCHAINS_HELPER_REMOTE_DIR = "/tmp/agent_scripts"
PROXYCHAINS_HELPER_REMOTE = f"{PROXYCHAINS_HELPER_REMOTE_DIR}/proxychains_common.sh"


def ensure_proxychains_runner(vm: VmConfig) -> str:
    helper = Path(__file__).resolve().parent / "agent_scripts" / "proxychains_common.sh"
    mkdir_command = ["multipass", "exec", vm.name, "--", "mkdir", "-p", PROXYCHAINS_HELPER_REMOTE_DIR]
    mkdir_result = subprocess.run(mkdir_command, check=False, capture_output=True, text=True)
    if mkdir_result.returncode != 0:
        raise MultipassError(
            tr(
                "vm.proxychains_helper_dir_failed",
                vm_name=vm.name,
                stdout=(mkdir_result.stdout or "").strip() or "-",
                stderr=(mkdir_result.stderr or "").strip() or "-",
            )
        )
    transfer_helper_command = ["multipass", "transfer", str(helper), f"{vm.name}:{PROXYCHAINS_HELPER_REMOTE}"]
    transfer_helper_result = subprocess.run(transfer_helper_command, check=False, capture_output=True, text=True)
    if transfer_helper_result.returncode != 0:
        raise MultipassError(
            tr(
                "vm.proxychains_helper_transfer_failed",
                vm_name=vm.name,
                stdout=(transfer_helper_result.stdout or "").strip() or "-",
                stderr=(transfer_helper_result.stderr or "").strip() or "-",
            )
        )

    runner = Path(__file__).resolve().parent / "run_with_proxychains.sh"
    transfer_command = ["multipass", "transfer", str(runner), f"{vm.name}:{PROXYCHAINS_RUNNER_REMOTE}"]
    transfer_result = subprocess.run(transfer_command, check=False, capture_output=True, text=True)
    if transfer_result.returncode != 0:
        raise MultipassError(
            tr(
                "vm.proxychains_transfer_failed",
                vm_name=vm.name,
                stdout=(transfer_result.stdout or "").strip() or "-",
                stderr=(transfer_result.stderr or "").strip() or "-",
            )
        )

    chmod_command = ["multipass", "exec", vm.name, "--", "chmod", "+x", PROXYCHAINS_RUNNER_REMOTE]
    chmod_result = subprocess.run(chmod_command, check=False, capture_output=True, text=True)
    if chmod_result.returncode != 0:
        raise MultipassError(
            tr(
                "vm.proxychains_chmod_failed",
                vm_name=vm.name,
                stdout=(chmod_result.stdout or "").strip() or "-",
                stderr=(chmod_result.stderr or "").strip() or "-",
            )
        )

    return PROXYCHAINS_RUNNER_REMOTE


def resolve_proxychains(vm: VmConfig, override: Optional[str]) -> Optional[str]:
    if override is None:
        return vm.proxychains

    cleaned = str(override).strip()
    if not cleaned:
        return None
    return cleaned


def _load_vms(path: Optional[str] = None) -> Dict[str, VmConfig]:
    config = load_config(Path(path) if path else None)
    return load_vms_config(config)


def create_vm_from_config(path: Optional[str], vm_name: str) -> tuple[str, Optional[str]]:
    vms = _load_vms(path)
    if vm_name not in vms:
        raise ConfigError(tr("vm.missing_in_config", vm_name=vm_name))

    ensure_multipass_available()
    existing_info = fetch_existing_info()

    target_vm = vms[vm_name]
    comparison = compare_vm(existing_info, target_vm.name, str(target_vm.cpu), target_vm.ram, target_vm.disk)
    status, _, details = comparison.partition(" ")
    if status == "mismatch":
        readable = _format_mismatch_details(details)
        return tr("vm.exists_continue", vm_name=target_vm.name), tr(
            "vm.mismatch_not_supported",
            vm_name=target_vm.name,
            details=readable,
        )
    if status == "match":
        return tr("vm.already_matches", vm_name=target_vm.name), None
    if status != "absent":
        raise MultipassError(tr("vm.status_unknown", vm_name=target_vm.name, response=comparison))

    ensure_resources_available(existing_info, [target_vm])

    return do_launch(target_vm, existing_info), None


def create_all_vms_from_config(path: Optional[str]) -> tuple[List[str], List[str]]:
    vms = _load_vms(path)

    ensure_multipass_available()
    existing_info = fetch_existing_info()

    planned: List[VmConfig] = []
    statuses: Dict[str, str] = {}
    mismatch_messages: List[str] = []

    for vm in vms.values():
        comparison = compare_vm(existing_info, vm.name, str(vm.cpu), vm.ram, vm.disk)
        status, _, details = comparison.partition(" ")
        if status == "mismatch":
            readable = _format_mismatch_details(details)
            mismatch_messages.append(tr("vm.mismatch_not_supported", vm_name=vm.name, details=readable))
        statuses[vm.name] = status
        if status == "absent":
            planned.append(vm)
        elif status not in {"match", "mismatch"}:
            raise MultipassError(tr("vm.status_unknown", vm_name=vm.name, response=comparison))

    if planned:
        ensure_resources_available(existing_info, planned)

    messages: List[str] = []
    for vm in planned:
        messages.append(do_launch(vm, existing_info))
        existing_info = fetch_existing_info()
    for name, status in statuses.items():
        if status == "match":
            messages.append(tr("vm.already_matches", vm_name=name))
        elif status == "mismatch":
            messages.append(tr("vm.exists_continue", vm_name=name))

    return messages, mismatch_messages
