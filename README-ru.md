[English README](README.md)

# Agent Safety Kit

Набор инструментов для запуска AI-агентов в изолированной среде внутри виртуальной машины Multipass.

## Немного ликбеза, если вы не понимаете зачем это:

<img width="437" height="379" alt="image" src="https://github.com/user-attachments/assets/c3486072-e96a-4197-8b1f-d6ac228c2cc6" />

Немного ссылок (нагуглить такого можно море):

* [Qwen Coder agent destroys working builds](https://github.com/QwenLM/qwen-code/issues/354)
* [Codex keeps deleting unrelated and uncommitted files! even ignoring rejected requests](https://github.com/openai/codex/issues/4969)
* [comment: qwen-code CLI destroyed my entire project, deleted important files](https://www.reddit.com/r/DeepSeek/comments/1mmfjsl/right_now_qwen_is_the_best_model_they_have_the/)
* [Claude Code deleted my entire workspace, here's the proof](https://www.reddit.com/r/ClaudeAI/comments/1m299f5/claude_code_deleted_my_entire_workspace_heres_the/)
* [I Asked Claude Code to Fix All Bugs, and It Deleted the Whole Repo](https://levelup.gitconnected.com/i-asked-claude-code-to-fix-all-bugs-and-it-deleted-the-whole-repo-e7f24f5390c5)
* [Codex has twice deleted and corrupted my files (r/ClaudeAI comment)](https://www.reddit.com/r/ClaudeAI/comments/1nhvyu0/openai_drops_gpt5_codex_cli_right_after/)

Понятно, что "все понимают" и "у всех должны быть бэкапы" и "у вас всё должно быть в git", но пока "песочница" которую предоставляют консольные ИИ-агенты не имеет встроенных снапшотов, позволяющих откатываться назад после каждой правки, сделанной ИИ, нужен некий инструмент, который позволит сделать это самостоятельно.

## Ключевые идеи

- Агент работает только в виртуальной машине.
- Виртуальная машина запускается через Multipass (это простой инструмент от Canonical для запуска ubuntu в виртуалке в 1 команду)
- Внутрь ВМ монтируются проектные папки из указанной пользователем директории; параллельно запускается автоматическое резервное копирование в соседнюю папку с настраиваемой частотой (по умолчанию раз в пять минут и только при изменениях), использующее `rsync` и hardlink'и для экономии места.
- Настройки виртуальной машины, монтирования и cloud-init задаются в YAML-конфиге.
- Агент можно запускать, не входя в гостевую систему через `multipass shell` — фактически он всё равно исполняется внутри ВМ.

## Быстрый старт

1. Склонируйте репозиторий и перейдите в него:
   ```bash
   git clone https://github.com/MihanEntalpo/agent-safety-kit/
   cd agent-safety-kit
   ```

2. Подготовьте Python-окружение и зависимости:
   ```bash
   python3 -m venv ./venv
   source ./venv/bin/activate
   pip install -r requirements.txt
   ```

3. Создайте YAML-конфигурацию (по умолчанию ищется `config.yaml`, путь можно переопределить через `CONFIG_PATH`):
   ```bash
   cp config-example.yaml config.yaml
   # отредактируйте параметры vms/mounts/cloud-init под себя
   ```

4. Установите необходимые системные зависимости (в частности, Multipass; потребуется sudo, работает пока только в debian-based системах):
   ```bash
   ./agsekit prepare
   ```

5. Создайте виртуальные машины с параметрами из YAML:
   ```bash
   ./agsekit create-vms
   ```

   Если нужно развернуть только одну ВМ, используйте `./agsekit create-vm <имя>`. Если ВМ уже существует, команда сравнит заданные ресурсы с текущими и сообщит об отличающихся параметрах. Пока изменить параметры уже работающей машины нельзя

6. Смонтируйте папки (предполагается, что монтирования уже описаны в YAML):
   ```bash
   ./agsekit mount --all
   ```

7. Установите все описанные агенты в их ВМ по умолчанию:
   ```bash
   ./agsekit setup-agents --all-agents
   ```

8. (Опционально) Запустите циклические бэкапы для всех монтирований, чтобы убедиться, что всё настроено корректно:
   ```bash
   ./agsekit backup-repeated-all --config config.yaml
   ```

9. Запустите агента внутри его ВМ (пример запускает `qwen` в его монтировании, бэкапы включены по умолчанию):
   ```bash
   ./agsekit run qwen /host/path/project --vm agent-ubuntu --config config.yaml -- --help
   ```

## Конфигурация YAML

`config.yaml` (или путь из `CONFIG_PATH`) описывает параметры ВМ, монтируемые директории и любые настройки `cloud-init`. Базовый пример есть в `config-example.yaml`:

```yaml
vms: # параметры виртуальных машин (можно иметь несколько)
  agent-ubuntu: # имя виртуальной машины
    cpu: 2      # количество vCPU
    ram: 4G     # объём оперативной памяти (поддерживаются 2G, 4096M и т.п.)
    disk: 20G   # размер диска
    cloud-init: {} # здесь можно разместить стандартный конфиг cloud-init, но он не обязателен
mounts:
  - source: /host/path/project            # путь к исходной папке на хосте
    target: /home/ubuntu/project          # точка монтирования внутри ВМ; если не указана, будет /home/ubuntu/<имя_папки_source>
    backup: /host/backups/project         # каталог для бэкапов; если не указан, будет backups-<имя_папки> рядом с source
    interval: 5                           # интервал бэкапа в минутах; по умолчанию 5
    vm: agent-ubuntu # имя VM, если не указан - берётся первая VM из конфигурации
agents:
  qwen: # имя агента, можно добавить столько, сколько нужно
    type: qwen-code # тип агента: qwen-code, codex-cli или claude-code (другие пока не поддерживаются)
    env: # произвольные переменные окружения, которые будут переданы агенту
      OPENAI_API_KEY: "my_local_key"
      OPENAI_BASE_URL: "https://127.0.0.1:11556/v1"
      OPENAI_MODEL: "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
    socks5_proxy: 10.0.0.2:1234 # при необходимости трафик агента будет идти через socks5-прокси посредством proxychains
    vm: qwen-ubuntu # ВМ по умолчанию для запуска агента; если не указана, берётся ВМ из монтирования или первая в списке
```


## Резервное копирование

### Разовая резервная копия

`./agsekit backup-once --source-dir <путь> --dest-dir <путь> [--exclude <паттерн> ...]` — однократный запуск резервного копирования исходной директории в указанную папку с помощью `rsync`.
Команда создаёт каталог с отметкой времени и суффиксом `-partial`, поддерживает инкрементальные копии через `--link-dest` на предыдущий бэкап и учитывает списки исключений из `.backupignore` и аргументов `--exclude`. После завершения выполнения временная папка переименовывается в финальную с тем же timestamp без суффикса. Если изменений относительно последнего бэкапа нет, новый снапшот не создаётся, и утилита сообщает об отсутствии обновлений.

Примеры строк для `.backupignore`:
```
# исключить виртуальные окружения и зависимости
venv/
node_modules/

# игнорировать временные и лог-файлы по маске
*.log
*.tmp

# вернуть в бэкап конкретный файл внутри исключённой папки
!logs/important.log

# пропустить артефакты сборки документации
docs/build/
```

Бэкап использует `rsync` с инкрементальными ссылками (`--link-dest`) на предыдущую копию: если изменился только небольшой набор файлов, в новой копии хранятся лишь изменённые данные, а неизменённые файлы представляют собой hardlink'и на прошлый снапшот. Это позволяет поддерживать цепочку датированных каталогов, занимая минимум места при редких изменениях.

### Циклические бэкапы

* `./agsekit backup-repeated --source-dir <путь> --dest-dir <путь> [--exclude <паттерн> ...] [--interval <минуты>]` — сразу делает бэкап и повторяет его каждые `interval` минут (по умолчанию каждые пять минут). После каждого запуска выводит `Done, waiting N minutes` с фактическим интервалом.
* `./agsekit backup-repeated-mount --mount <путь> [--config <путь>]` — ищет монтирование по полю `source` в `config.yaml` (или по пути из `CONFIG_PATH`/`--config`) и запускает циклические бэкапы с путями и интервалом из конфига. Если монтирования нет — ошибка.
* `./agsekit backup-repeated-all [--config <путь>]` — читает все монтирования из конфига (по умолчанию `config.yaml` или путь из `CONFIG_PATH`/`--config`) и поднимает одновременные циклические бэкапы для каждого из них в одном процессе. Остановить можно через Ctrl+C.

### Управление монтированиями

* `./agsekit mount --source-dir <путь> [--config <путь>]` — монтирует директорию с `source` из `config.yaml` (или пути из `CONFIG_PATH`/`--config`) в её ВМ через `multipass mount`. Флаг `--all` монтирует все записи из конфига.
* `./agsekit umount --source-dir <путь> [--config <путь>]` — отмонтирует директорию с `source` из конфига (или `CONFIG_PATH`/`--config`); `--all` отмонтирует все настроенные пути.

### Установка агентов

* `./agsekit setup-agents <agent_name> [<vm>|--all-vms] [--config <path>]` — запускает подготовленный скрипт установки для выбранного типа агента внутри указанной ВМ (или ВМ по умолчанию для агента, если не задана).
* `./agsekit setup-agents --all-agents [--all-vms] [--config <path>]` — устанавливает всех описанных агентов либо в их ВМ по умолчанию, либо во все ВМ при указании `--all-vms`.

Скрипты установки лежат в `agsekit_cli/agent_scripts/` и повторяют стандартные шаги для codex-cli, qwen-code и claude-code. Другие типы агентов пока не поддерживаются.

### Запуск агентов

* `./agsekit run <agent_name> [<source_dir>|--vm <vm_name>] [--config <path>] [--disable-backups] -- <agent_args...>` — запускает интерактивную команду агента внутри Multipass. Переменные окружения из конфига передаются процессу. Если указан `source_dir` из списка монтирований, запуск произойдёт в соответствующей ВМ и целевой директории монтирования; иначе агент стартует в домашней папке ВМ по умолчанию. При отсутствии флага `--disable-backups` параллельно поднимается фоновый повторяющийся бэкап для выбранного монтирования на время работы агента.
