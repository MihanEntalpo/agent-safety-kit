from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .config import load_config, load_vm_config

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


def do_launch(vm_config: Dict[str, object]) -> str:
    name = str(vm_config["name"])
    cpus = str(vm_config["cpu"])
    mem = str(vm_config["ram"])
    disk = str(vm_config["disk"])

    ensure_multipass_available()

    existing_info = fetch_existing_info()
    comparison_result = compare_vm(existing_info, name, cpus, mem, disk)

    status, _, details = comparison_result.partition(" ")
    if status == "mismatch":
        readable = details.replace(";", ", ").replace("cpus", "CPU").replace("memory", "память").replace("disk", "диск")
        raise MultipassError(
            f"ВМ {name} уже существует, но изменение ее параметров пока не поддерживается. Несовпадающие параметры: {readable}."
        )
    if status == "match":
        return f"ВМ {name} уже существует и соответствует заданным параметрам."
    if status != "absent":
        raise MultipassError(f"Не удалось определить состояние ВМ {name}. Получен ответ: {comparison_result}")

    launch_cmd = ["multipass", "launch", "--name", name, "--cpus", cpus, "--memory", mem, "--disk", disk]
    launch_result = subprocess.run(launch_cmd, check=False, capture_output=True, text=True)
    if launch_result.returncode != 0:
        raise MultipassError(launch_result.stderr.strip() or "Не удалось создать ВМ")
    return f"ВМ {name} создана."


def create_vm_from_config(path: Optional[str] = None) -> str:
    config = load_config(Path(path) if path else None)
    vm_config = load_vm_config(config)
    return do_launch(vm_config)
