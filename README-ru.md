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
   git clone https://github.com/<your-org>/agent-safety-kit.git
   cd agent-safety-kit
   ```

2. Подготовьте Python-окружение и зависимости:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
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
