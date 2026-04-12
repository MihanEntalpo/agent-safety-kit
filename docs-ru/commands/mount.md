# Команды монтирования

## Команды

```bash
agsekit mount [SOURCE_DIR] [--all] [--config <path>] [--non-interactive] [--debug]
agsekit umount [SOURCE_DIR] [--all] [--config <path>] [--non-interactive] [--debug]
agsekit addmount [SOURCE_DIR] [TARGET_DIR] [BACKUP_DIR] [INTERVAL] [--vm <vm_name>] [--max-backups <count>] [--backup-clean-method tail|thin] [--mount] [--allowed-agents <a,b,c>] [-y] [--config <path>] [--non-interactive] [--debug]
agsekit removemount [SOURCE_DIR] [--vm <vm_name>] [-y] [--config <path>] [--non-interactive] [--debug]
```

Общие аргументы:

- `--config <path>` - путь к YAML-конфигу. Если не указан, используется `CONFIG_PATH` или `~/.config/agsekit/config.yaml`.
- `--non-interactive` - отключает интерактивные prompt'ы. Для `mount` и `umount` сейчас почти не влияет на поведение, но для `addmount` и `removemount` делает обязательными параметры, которые иначе можно было бы спросить.
- `--debug` - печатает выполняемые команды и диагностический вывод.

## `mount`

Монтирует хостовую директорию, указанную в конфигурации, в соответствующую VM.

Сигнатура:

```bash
agsekit mount [SOURCE_DIR] [--all] [--config <path>] [--non-interactive] [--debug]
```

Аргументы:

- `SOURCE_DIR` - путь к папке на хосте. Команда ищет подходящую запись `mounts[]` по `source`; можно указать сам `source` или подпапку внутри него.
- `--all` - примонтировать все записи из `mounts[]`.
- `--config <path>` - какой YAML-конфиг читать.
- `--non-interactive` - общий флаг CLI; у этой команды не добавляет отдельных prompt'ов.
- `--debug` - показать команды Multipass и отладочный вывод.

Правила выбора:

- `SOURCE_DIR` и `--all` нельзя указывать вместе.
- Если `SOURCE_DIR` не указан и в конфиге один mount, используется он.
- Если `SOURCE_DIR` не указан и mount'ов несколько, команда просит указать путь или `--all`.
- Если mount уже зарегистрирован в Multipass, команда пишет об этом и не падает.

Примеры:

```bash
agsekit mount /path/to/project
agsekit mount --all
```

## `umount`

Размонтирует настроенный mount из VM.

Сигнатура:

```bash
agsekit umount [SOURCE_DIR] [--all] [--config <path>] [--non-interactive] [--debug]
```

Аргументы:

- `SOURCE_DIR` - путь к папке на хосте. Команда ищет подходящую запись `mounts[]` по `source`; можно указать сам `source` или подпапку внутри него.
- `--all` - размонтировать все записи из `mounts[]`.
- `--config <path>` - какой YAML-конфиг читать.
- `--non-interactive` - общий флаг CLI; у этой команды не добавляет отдельных prompt'ов.
- `--debug` - показать команды Multipass и отладочный вывод.

Правила выбора такие же, как у `mount`: `SOURCE_DIR` и `--all` конфликтуют, один mount выбирается автоматически, при нескольких mount'ах нужен путь или `--all`.

Примеры:

```bash
agsekit umount /path/to/project
agsekit umount --all
```

## `addmount`

Добавляет mount entry в YAML-конфиг и при необходимости может сразу примонтировать его.

Имеет удобный интерактивный режим, можно выполнить просто как:
```shell
agsekit addmount [SOURCE_DIR]
```

Сигнатура:

```bash
agsekit addmount [SOURCE_DIR] [TARGET_DIR] [BACKUP_DIR] [INTERVAL] [--vm <vm_name>] [--max-backups <count>] [--backup-clean-method tail|thin] [--mount] [--allowed-agents <a,b,c>] [-y] [--config <path>] [--non-interactive] [--debug]
```

Позиционные аргументы:

- `SOURCE_DIR` - папка на хосте, которую нужно добавить в `mounts[].source`. В интерактивном режиме, если не указана, спрашивается prompt с текущей папкой по умолчанию. В non-interactive режиме обязательна.
- `TARGET_DIR` - путь внутри VM для `mounts[].target`. Если не указан, используется `/home/ubuntu/<имя SOURCE_DIR>`.
- `BACKUP_DIR` - папка на хосте для `mounts[].backup`. Если не указана, используется `<родитель SOURCE_DIR>/backups-<имя SOURCE_DIR>`.
- `INTERVAL` - значение `mounts[].interval`, интервал бэкапов в минутах. Если не указан, по умолчанию `5`; в интерактивном режиме спрашивается prompt.

Опции:

- `--vm <vm_name>` - значение `mounts[].vm`, VM для новой записи. Если в конфиге одна VM, она выбирается автоматически. Если VM несколько и флаг не указан, в интерактивном режиме будет prompt, а в non-interactive режиме будет выбрана первая VM из секции `vms`.
- `--max-backups <count>` - значение `mounts[].max_backups`, сколько снапшотов хранить. По умолчанию `100`; значение должно быть положительным.
- `--backup-clean-method tail|thin` - значение `mounts[].backup_clean_method`. По умолчанию `thin`.
- `--mount` - сразу выполнить `multipass mount` после сохранения записи.
- `--allowed-agents <a,b,c>` - записать `mounts[].allowed_agents`, список разрешённых агентов через запятую. Имена должны существовать в секции `agents`.
- `-y`, `--yes` - пропустить подтверждение перед изменением конфига. В non-interactive режиме нужен, иначе команда завершится ошибкой на этапе подтверждения.
- `--config <path>` - какой YAML-конфиг изменить.
- `--non-interactive` - отключить prompt'ы и использовать переданные/default значения.
- `--debug` - показать отладочный вывод.

Что записывается в конфиг:

- `source`
- `vm`
- `target`
- `backup`
- `interval`
- `max_backups`
- `backup_clean_method`
- `allowed_agents`, если он был задан или выбран интерактивно

Перед записью команда показывает summary, проверяет, что такого `source + vm` ещё нет, создаёт timestamp backup YAML-файла рядом с конфигом и сохраняет файл с сохранением комментариев.

Если `--mount` не передан, но команда работает интерактивно, после сохранения будет вопрос: `Сразу примонтировать папку? [Y/n]`. По умолчанию ответ yes.

## `removemount`

Удаляет mount entry из конфига. CLI сначала пытается размонтировать mount и сохраняет конфиг без изменений, если размонтирование не удалось.

Сигнатура:

```bash
agsekit removemount [SOURCE_DIR] [--vm <vm_name>] [-y] [--config <path>] [--non-interactive] [--debug]
```

Аргументы:

- `SOURCE_DIR` - `mounts[].source`, который нужно удалить. Сравнение идёт по нормализованному абсолютному пути. В интерактивном режиме, если путь не указан, команда предложит выбрать mount из списка. В non-interactive режиме путь обязателен.
- `--vm <vm_name>` - уточнить VM, если есть несколько mount-записей с одинаковым `source`, но разными VM.
- `-y`, `--yes` - пропустить подтверждение перед удалением. В non-interactive режиме нужен, иначе команда завершится ошибкой на этапе подтверждения.
- `--config <path>` - какой YAML-конфиг изменить.
- `--non-interactive` - отключить prompt выбора mount и prompt подтверждения.
- `--debug` - показать команды Multipass и отладочный вывод.

Правила выбора:

- Если `SOURCE_DIR` найден ровно в одной записи, удаляется она.
- Если найдено несколько записей с тем же `SOURCE_DIR`, используйте `--vm <vm_name>`; в интерактивном режиме можно выбрать запись из списка.
- Если `SOURCE_DIR` не указан, интерактивный режим предложит выбор из всех mount'ов, non-interactive режим завершится ошибкой.

Порядок действий:

1. Команда показывает summary выбранного mount.
2. Если не передан `-y`, спрашивает подтверждение.
3. Сначала выполняет `umount` выбранного mount.
4. Только после успешного `umount` удаляет запись из YAML.
5. Перед сохранением создаёт timestamp backup конфига рядом с YAML-файлом.

## См. также

- [Конфигурация](../configuration.md)
- [Бэкапы](../backups.md)
- [run](run.md)
