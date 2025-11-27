import json
import os
import re
import sys
from typing import Dict, List, Optional

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


def main() -> int:
    raw_info = sys.stdin.read()
    try:
        name = os.environ["VM_NAME"]
        expected_cpus = os.environ["VM_CPUS"]
        expected_mem_raw = os.environ["VM_MEM"]
        expected_disk_raw = os.environ["VM_DISK"]
    except KeyError as exc:
        missing = exc.args[0]
        print(f"missing_env {missing}")
        return 2

    print(compare_vm(raw_info, name, expected_cpus, expected_mem_raw, expected_disk_raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())
