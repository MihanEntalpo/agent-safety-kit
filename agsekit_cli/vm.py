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
        raise MultipassError("Multipass не установлен. Сначала запустите ./agsekit prepare.")


def fetch_existing_info() -> str:
    result = subprocess.run([
        "multipass",
        "list",
        "--format",
        "json",
    ], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise MultipassError(result.stderr.strip() or "Не удалось получить список ВМ multipass")
    return result.stdout


def _system_cpu_count() -> int:
    cpu_count = os.cpu_count()
    if cpu_count is None:
        raise MultipassError("Не удалось определить количество CPU в системе")
    return cpu_count


def _system_memory_bytes() -> int:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")  # type: ignore[arg-type]
        page_count = os.sysconf("SC_PHYS_PAGES")  # type: ignore[arg-type]
        return int(page_size) * int(page_count)
    except (AttributeError, ValueError, OSError):
        raise MultipassError("Не удалось определить объем оперативной памяти системы")


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
            raise ConfigError(f"Не удалось разобрать объем памяти для ВМ {vm.name}: {vm.ram}")
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
        raise MultipassError(
            "Недостаточно ресурсов для создания ВМ: после выделения должно оставаться минимум 1 CPU и 1 ГБ RAM."
        )


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
        readable = details.replace(";", ", ").replace("cpus", "CPU").replace("memory", "память").replace("disk", "диск")
        raise MultipassError(
            f"ВМ {vm_config.name} уже существует, но изменение ее параметров пока не поддерживается. Несовпадающие параметры: {readable}."
        )
    if status == "match":
        return f"ВМ {vm_config.name} уже существует и соответствует заданным параметрам."
    if status != "absent":
        raise MultipassError(f"Не удалось определить состояние ВМ {vm_config.name}. Получен ответ: {comparison_result}")

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
        raise MultipassError(launch_result.stderr.strip() or "Не удалось создать ВМ")
    return f"ВМ {vm_config.name} создана."


def build_port_forwarding_args(rules: Iterable[PortForwardingRule]) -> List[str]:
    args: List[str] = []
    for rule in rules:
        if rule.type == "local":
            args.extend(["-L", f"{rule.host_addr}:{rule.vm_addr}"])
        elif rule.type == "remote":
            args.extend(["-R", f"{rule.host_addr}:{rule.vm_addr}"])
        elif rule.type == "socks5":
            args.extend(["-D", rule.vm_addr])
    return args


def wrap_with_proxychains(command: List[str], proxychains: Optional[str]) -> List[str]:
    if proxychains is None:
        return command

    proxychains_value = str(proxychains).strip()
    if not proxychains_value:
        return command

    runner = Path(__file__).resolve().parent / "run_with_proxychains.sh"
    return ["bash", str(runner), "--proxy", proxychains_value, *command]


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


def create_vm_from_config(path: Optional[str], vm_name: str) -> str:
    vms = _load_vms(path)
    if vm_name not in vms:
        raise ConfigError(f"В конфигурации нет ВМ с именем {vm_name}")

    ensure_multipass_available()
    existing_info = fetch_existing_info()

    target_vm = vms[vm_name]
    comparison = compare_vm(existing_info, target_vm.name, str(target_vm.cpu), target_vm.ram, target_vm.disk)
    status, _, details = comparison.partition(" ")
    if status == "mismatch":
        readable = details.replace(";", ", ").replace("cpus", "CPU").replace("memory", "память").replace("disk", "диск")
        raise MultipassError(
            f"ВМ {target_vm.name} уже существует, но изменение ее параметров пока не поддерживается. Несовпадающие параметры: {readable}."
        )
    if status == "match":
        return f"ВМ {target_vm.name} уже существует и соответствует заданным параметрам."
    if status != "absent":
        raise MultipassError(f"Не удалось определить состояние ВМ {target_vm.name}. Получен ответ: {comparison}")

    ensure_resources_available(existing_info, [target_vm])

    return do_launch(target_vm, existing_info)


def create_all_vms_from_config(path: Optional[str]) -> List[str]:
    vms = _load_vms(path)

    ensure_multipass_available()
    existing_info = fetch_existing_info()

    planned: List[VmConfig] = []
    statuses: Dict[str, str] = {}

    for vm in vms.values():
        comparison = compare_vm(existing_info, vm.name, str(vm.cpu), vm.ram, vm.disk)
        status, _, details = comparison.partition(" ")
        if status == "mismatch":
            readable = details.replace(";", ", ").replace("cpus", "CPU").replace("memory", "память").replace("disk", "диск")
            raise MultipassError(
                f"ВМ {vm.name} уже существует, но изменение ее параметров пока не поддерживается. Несовпадающие параметры: {readable}."
            )
        statuses[vm.name] = status
        if status == "absent":
            planned.append(vm)
        elif status not in {"match", "mismatch"}:
            raise MultipassError(f"Не удалось определить состояние ВМ {vm.name}. Получен ответ: {comparison}")

    if planned:
        ensure_resources_available(existing_info, planned)

    messages: List[str] = []
    for vm in planned:
        messages.append(do_launch(vm, existing_info))
        existing_info = fetch_existing_info()
    for name, status in statuses.items():
        if status == "match":
            messages.append(f"ВМ {name} уже существует и соответствует заданным параметрам.")

    return messages
