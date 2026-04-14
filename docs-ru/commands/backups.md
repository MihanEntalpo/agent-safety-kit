# Backup-команды

По умолчанию о бэкапах можно не беспокоиться, `agsekit run <agent>` запускает бэкапы автоматически, и они делаются каждые 5 минут (по умолчанию) в ходе работы агента.

Тем не менее можно запускать бэкапы "вручную" с помощью имеющихся команд, если это нужно для каких-то скриптов.

Все команды бэкапов принимают во внимание файлы `.backupignore` которые аналогичны файлам `.gitignore` по структуре, и указывают, что именно не надо копировать

## Содержание

- [`backup-once`](#backup-once)
- [`backup-repeated`](#backup-repeated)
- [`backup-repeated-mount`](#backup-repeated-mount)
- [`backup-repeated-all`](#backup-repeated-all)
- [`backup-clean`](#backup-clean)
- [Во время `agsekit run`](#во-время-agsekit-run)

## Команды

Команды с аргументом `--config` ищут mount в YAML-конфиге и берут оттуда часть параметров: `mounts[].source`, `mounts[].backup`, `mounts[].interval`, `mounts[].max_backups`, `mounts[].backup_clean_method`.

## `backup-once`

```shell
agsekit backup-once --source-dir <path> --dest-dir <path> [--exclude <pattern>]... [--progress]
```

Создаёт один snapshot в целевом каталоге. Если относительно предыдущего снапшота ничего не изменилось, новый снапшот не создаётся.

Отображает прогресс резервного копирования.

Аргументы:

- `--source-dir <path>` - исходная папка на хосте.
- `--dest-dir <path>` - папка на хосте, куда складывается backup-цепочка.
- `--exclude <pattern>` - дополнительное правило исключения для `rsync`; можно передать несколько раз. Добавляется к правилам из `.backupignore`.
- `--progress` - показать progress bar копирования.

Эта команда не читает mount-настройки из конфига. Пути, исключения и progress-режим задаются аргументами команды.

Cleanup после создания снапшота здесь не запускается.

## `backup-repeated`

```shell
agsekit backup-repeated --source-dir <path> --dest-dir <path> [--exclude <pattern>]... [--interval <minutes>] [--max-backups <count>] [--backup-clean-method tail|thin] [--skip-first]
```

Запускает бэкапы по таймеру.

Аргументы:

- `--source-dir <path>` - исходная папка на хосте.
- `--dest-dir <path>` - папка на хосте, куда складывается backup-цепочка.
- `--exclude <pattern>` - дополнительное правило исключения для `rsync`; можно передать несколько раз. Добавляется к правилам из `.backupignore`.
- `--interval <minutes>` - интервал между снапшотами в минутах. По умолчанию `5`.
- `--max-backups <count>` - сколько снапшотов оставить после очистки. По умолчанию `100`.
- `--backup-clean-method tail|thin` - метод очистки. По умолчанию `thin`.
- `--skip-first` - сначала подождать один интервал, а не делать снапшот сразу.

Если команда запускается вручную, `--interval`, `--max-backups` и `--backup-clean-method` берутся из аргументов команды. Когда эту команду запускает `agsekit run`, эти значения берутся из выбранного mount в конфиге.

Cleanup запускается после каждого backup-цикла.

## `backup-repeated-mount`

```shell
agsekit backup-repeated-mount --mount <path> [--config <path>]
```

Резолвит пути и policy из настроенной mount entry.

Аргументы:

- `--mount <path>` - `mounts[].source`, для которого нужно запустить бэкапы. Если mount в конфиге один, аргумент можно не указывать. Если mount'ов несколько, аргумент обязателен.
- `--config <path>` - путь к YAML-конфигу. Если не указан, используется `CONFIG_PATH` или `~/.config/agsekit/config.yaml`.

Из найденного mount берутся:

- `mounts[].source` - исходная папка.
- `mounts[].backup` - папка backup-цепочки.
- `mounts[].interval` - интервал между снапшотами.
- `mounts[].max_backups` - сколько снапшотов оставлять.
- `mounts[].backup_clean_method` - метод очистки.

Cleanup запускается после каждого backup-цикла.

## `backup-repeated-all`

```shell
agsekit backup-repeated-all [--config <path>]
```

Запускает repeated backup loops для всех mount из конфига.

Аргументы:

- `--config <path>` - путь к YAML-конфигу. Если не указан, используется `CONFIG_PATH` или `~/.config/agsekit/config.yaml`.

Для каждой записи `mounts[]` используются её параметры `source`, `backup`, `interval`, `max_backups` и `backup_clean_method`.

Cleanup запускается после каждого backup-цикла в каждом запущенном loop.

## `backup-clean`

```shell
agsekit backup-clean <mount_source> [<keep>] [<method>] [--config <path>]
```

Чистит старые снапшоты по policy `tail` или `thin`.

Аргументы:

- `<mount_source>` - исходная папка mount, то есть значение `mounts[].source`.
- `<keep>` - сколько снапшотов оставить. По умолчанию `50`. Это значение задаётся аргументом команды и не берётся из `mounts[].max_backups`.
- `<method>` - метод очистки: `thin` или `tail`. По умолчанию `thin`. Это значение задаётся аргументом команды и не берётся из `mounts[].backup_clean_method`.
- `--config <path>` - путь к YAML-конфигу. Если не указан, используется `CONFIG_PATH` или `~/.config/agsekit/config.yaml`.

Из конфига команда берёт `mounts[].backup` для найденного `mounts[].source`. Для метода `thin` также используется `mounts[].interval`, потому что интервал влияет на прореживание истории.

## Во время `agsekit run`

Если `agsekit run` запущен из mount-папки и не передан аргумент `--disable-backups`:

1. Если в `mounts[].backup` ещё нет снапшотов, `run` создаёт initial snapshot внутренним вызовом backup-логики, пока этот backup делается - пользователь вынужден подождать. 
2. После initial snapshot сразу выполняется cleanup по `mounts[].max_backups` и `mounts[].backup_clean_method`.
3. Затем `run` запускает фоновую CLI-команду `backup-repeated`.
4. В `backup-repeated` передаются параметры выбранного mount из конфига: `mounts[].source`, `mounts[].backup`, `mounts[].interval`, `mounts[].max_backups`, `mounts[].backup_clean_method`.
5. Если initial snapshot уже был создан, фоновый `backup-repeated` стартует с `--skip-first`.

Если `run` работает во временной непремонтированной папке или передан `--disable-backups`, backup-команды не запускаются.

## См. также

- [Обзор бэкапов](../backups.md)
- [run](run.md)
