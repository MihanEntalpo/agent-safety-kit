#!/usr/bin/env bash
# Общие вспомогательные функции для bash-скриптов проекта.

# Загружает переменные окружения из файла, если они отсутствуют в текущей среде.
#
# Использование:
#   load_env_if_needed path/to/.env VAR1 VAR2 ...
#
# Если файл отсутствует или после загрузки остаются незаданные обязательные
# переменные, функция завершает процесс с кодом 1 и печатает сообщение в stderr.
load_env_if_needed() {
  local env_file="$1"
  shift
  local required=("$@")

  local missing=()
  for var in "${required[@]}"; do
    if [[ -z "${!var:-}" ]]; then
      missing+=("$var")
    fi
  done

  if (( ${#missing[@]} == 0 )); then
    return
  fi

  if [[ ! -f "$env_file" ]]; then
    echo "Не хватает переменных: ${missing[*]}. Файл $env_file не найден. Создайте его на основе example.env или экспортируйте переменные окружения." >&2
    exit 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a

  local still_missing=()
  for var in "${required[@]}"; do
    if [[ -z "${!var:-}" ]]; then
      still_missing+=("$var")
    fi
  done

  if (( ${#still_missing[@]} > 0 )); then
    echo "Не найдены обязательные переменные: ${still_missing[*]}." >&2
    exit 1
  fi
}
