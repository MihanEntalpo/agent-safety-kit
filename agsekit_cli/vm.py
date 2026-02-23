from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml

from .config import ConfigError, PortForwardingRule, VmConfig, load_config, load_vms_config
from .debug import debug_log_command, debug_log_result
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

RESOURCE_SIZE_RELATIVE_TOLERANCE = 0.10


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


def _to_bytes_deep(value: object) -> Optional[int]:
    direct = to_bytes(value)
    if direct is not None:
        return direct

    if not isinstance(value, dict):
        return None

    for key in ("total", "size", "limit", "max"):
        if key in value:
            parsed = _to_bytes_deep(value[key])
            if parsed is not None:
                return parsed

    nested_totals: List[int] = []
    for nested in value.values():
        if isinstance(nested, dict):
            parsed = _to_bytes_deep(nested)
            if parsed is not None:
                nested_totals.append(parsed)
    if nested_totals:
        return sum(nested_totals)
    return None


def _fetch_runtime_info_entry(name: str) -> Optional[Dict[str, object]]:
    command = ["multipass", "info", name, "--format", "json"]
    debug_log_command(command)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    debug_log_result(result)
    if result.returncode != 0:
        return None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    info = payload.get("info")
    if not isinstance(info, dict):
        return None
    entry = info.get(name)
    if not isinstance(entry, dict):
        return None
    return entry


def _extract_cpu_count(list_entry: Dict[str, object], info_entry: Optional[Dict[str, object]]) -> Optional[str]:
    for source in (list_entry, info_entry):
        if not source:
            continue
        for key in ("cpus", "cpu_count", "cpu-count"):
            value = source.get(key)
            if isinstance(value, (int, float)):
                return str(int(value))
            if isinstance(value, str) and value.strip():
                return value.strip()
        cpu_payload = source.get("cpu")
        if isinstance(cpu_payload, dict):
            count = cpu_payload.get("count")
            if isinstance(count, (int, float)):
                return str(int(count))
            if isinstance(count, str) and count.strip():
                return count.strip()
    return None


def _extract_ram_bytes(list_entry: Dict[str, object], info_entry: Optional[Dict[str, object]]) -> Optional[int]:
    candidates: List[object] = [
        list_entry.get("mem"),
        list_entry.get("memory"),
        list_entry.get("memory_total"),
        list_entry.get("ram"),
    ]
    if info_entry:
        candidates.extend(
            [
                info_entry.get("memory"),
                info_entry.get("mem"),
                info_entry.get("memory_total"),
                info_entry.get("ram"),
            ]
        )

    for candidate in candidates:
        if candidate is None:
            continue
        parsed = _to_bytes_deep(candidate)
        if parsed is not None:
            return parsed
    return None


def _extract_disk_bytes(list_entry: Dict[str, object], info_entry: Optional[Dict[str, object]]) -> Optional[int]:
    candidates: List[object] = [
        list_entry.get("disk"),
        list_entry.get("disk_total"),
        list_entry.get("disk_space"),
    ]
    if info_entry:
        candidates.extend(
            [
                info_entry.get("disk"),
                info_entry.get("disks"),
                info_entry.get("disk_total"),
            ]
        )

    for candidate in candidates:
        if candidate is None:
            continue
        parsed = _to_bytes_deep(candidate)
        if parsed is not None:
            return parsed
    return None


def _resource_size_matches(actual: Optional[int], expected: Optional[int]) -> bool:
    if actual is None or expected is None:
        return True
    if actual == expected:
        return True

    # Multipass reports effective resource sizes that can be lower than requested.
    delta = abs(actual - expected)
    return (delta / max(expected, 1)) <= RESOURCE_SIZE_RELATIVE_TOLERANCE


def compare_vm(
    raw_info: str,
    name: str,
    expected_cpus: str,
    expected_mem_raw: str,
    expected_disk_raw: str,
    runtime_info: Optional[Dict[str, object]] = None,
) -> str:
    entry = load_existing_entry(raw_info, name)
    if entry is None:
        return "absent"

    runtime_entry = runtime_info or _fetch_runtime_info_entry(name)

    current_cpus = _extract_cpu_count(entry, runtime_entry)
    current_mem = _extract_ram_bytes(entry, runtime_entry)
    current_disk = _extract_disk_bytes(entry, runtime_entry)

    expected_mem = to_bytes(expected_mem_raw)
    expected_disk = to_bytes(expected_disk_raw)

    mismatches: List[str] = []
    if current_cpus is not None and str(current_cpus) != str(expected_cpus):
        mismatches.append("cpus")
    if not _resource_size_matches(current_mem, expected_mem):
        mismatches.append("memory")
    if not _resource_size_matches(current_disk, expected_disk):
        mismatches.append("disk")

    if mismatches:
        return f"mismatch {';'.join(mismatches)}"
    return "match"


def ensure_multipass_available() -> None:
    if shutil.which("multipass") is None:
        raise MultipassError(tr("vm.multipass_missing"))


def fetch_existing_info() -> str:
    command = [
        "multipass",
        "list",
        "--format",
        "json",
    ]
    debug_log_command(command)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    debug_log_result(result)
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


def _is_transient_launch_error(stderr: str) -> bool:
    normalized = stderr.lower()
    return "remote" in normalized and "unknown or unreachable" in normalized


def _warm_multipass_catalog() -> None:
    command = ["multipass", "find"]
    debug_log_command(command)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    debug_log_result(result)


def _launch_with_retries(launch_cmd: List[str], max_attempts: int = 3) -> subprocess.CompletedProcess[str]:
    last_result: Optional[subprocess.CompletedProcess[str]] = None
    for attempt in range(1, max_attempts + 1):
        debug_log_command(launch_cmd)
        result = subprocess.run(launch_cmd, check=False, capture_output=True, text=True)
        debug_log_result(result)
        last_result = result
        if result.returncode == 0:
            return result

        stderr = (result.stderr or "").strip()
        if attempt < max_attempts and _is_transient_launch_error(stderr):
            _warm_multipass_catalog()
            time.sleep(min(2 * attempt, 5))
            continue
        return result

    assert last_result is not None
    return last_result


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
        launch_result = _launch_with_retries(launch_cmd)
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


def _copy_file_into_vm_via_stdin(local_path: Path, remote_path: str, vm_name: str, error_key: str) -> None:
    try:
        payload = local_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MultipassError(tr(error_key, vm_name=vm_name, stdout="-", stderr=str(exc)))

    upload_command = [
        "multipass",
        "exec",
        vm_name,
        "--",
        "bash",
        "-lc",
        f"cat > {shlex.quote(remote_path)}",
    ]
    debug_log_command(upload_command)
    upload_result = subprocess.run(
        upload_command,
        check=False,
        capture_output=True,
        text=True,
        input=payload,
    )
    debug_log_result(upload_result)
    if upload_result.returncode != 0:
        raise MultipassError(
            tr(
                error_key,
                vm_name=vm_name,
                stdout=(upload_result.stdout or "").strip() or "-",
                stderr=(upload_result.stderr or "").strip() or "-",
            )
        )


def ensure_proxychains_runner(vm: VmConfig) -> str:
    helper = Path(__file__).resolve().parent / "agent_scripts" / "proxychains_common.sh"
    mkdir_command = ["multipass", "exec", vm.name, "--", "mkdir", "-p", PROXYCHAINS_HELPER_REMOTE_DIR]
    debug_log_command(mkdir_command)
    mkdir_result = subprocess.run(mkdir_command, check=False, capture_output=True, text=True)
    debug_log_result(mkdir_result)
    if mkdir_result.returncode != 0:
        raise MultipassError(
            tr(
                "vm.proxychains_helper_dir_failed",
                vm_name=vm.name,
                stdout=(mkdir_result.stdout or "").strip() or "-",
                stderr=(mkdir_result.stderr or "").strip() or "-",
            )
        )
    _copy_file_into_vm_via_stdin(helper, PROXYCHAINS_HELPER_REMOTE, vm.name, "vm.proxychains_helper_transfer_failed")

    runner = Path(__file__).resolve().parent / "run_with_proxychains.sh"
    _copy_file_into_vm_via_stdin(runner, PROXYCHAINS_RUNNER_REMOTE, vm.name, "vm.proxychains_transfer_failed")

    chmod_command = ["multipass", "exec", vm.name, "--", "chmod", "+x", PROXYCHAINS_RUNNER_REMOTE]
    debug_log_command(chmod_command)
    chmod_result = subprocess.run(chmod_command, check=False, capture_output=True, text=True)
    debug_log_result(chmod_result)
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
