#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=".env"
REQUIRED_VARS=(VM_NAME VM_CPUS VM_MEM VM_DISK)

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/utils.sh"

load_env_if_needed "$ENV_FILE" "${REQUIRED_VARS[@]}"

if ! command -v multipass >/dev/null 2>&1; then
  echo "Multipass не установлен. Сначала запустите ./install_multipass.sh." >&2
  exit 1
fi

existing_info=$(multipass list --format json 2>/dev/null || true)

comparison_result=$(python "$SCRIPT_DIR/lib/compare_vm_properties.py" <<<"${existing_info}")
comparison_status=${comparison_result%% *}
comparison_details=${comparison_result#* }

if [[ "$comparison_status" == "$comparison_details" ]]; then
  comparison_details=""
fi

if [[ "$comparison_status" == "absent" ]]; then
  echo "Создаем новую виртуальную машину ${VM_NAME}..."
  multipass launch --name "$VM_NAME" --cpus "$VM_CPUS" --memory "$VM_MEM" --disk "$VM_DISK"
  echo "ВМ ${VM_NAME} создана."
elif [[ "$comparison_status" == "match" ]]; then
  echo "ВМ ${VM_NAME} уже существует и соответствует заданным параметрам."
elif [[ "$comparison_status" == "mismatch" ]]; then
  readable_details=${comparison_details//;/, }
  readable_details=${readable_details//cpus/CPU}
  readable_details=${readable_details//memory/память}
  readable_details=${readable_details//disk/диск}
  echo "ВМ ${VM_NAME} уже существует, но изменение ее параметров пока не поддерживается. Несовпадающие параметры: ${readable_details}." >&2
  exit 1
else
  echo "Не удалось определить состояние ВМ ${VM_NAME}. Получен ответ: ${comparison_result}" >&2
  exit 1
fi
