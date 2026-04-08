# Команды монтирования

## Команды

```bash
agsekit mount --source-dir <path> [--config <path>] [--debug]
agsekit umount --source-dir <path> [--config <path>] [--debug]
agsekit addmount <path> [...] [--config <path>] [--mount] [-y] [--debug]
agsekit removemount [<path>] [--config <path>] [--vm <vm_name>] [-y] [--debug]
```

## `mount`

Монтирует настроенную хостовую директорию в соответствующую VM.

Полезные формы:

```bash
agsekit mount --source-dir /path/to/project
agsekit mount --all
```

## `umount`

Размонтирует настроенный mount из VM.

Полезные формы:

```bash
agsekit umount --source-dir /path/to/project
agsekit umount --all
```

## `addmount`

Добавляет mount entry в YAML-конфиг и при необходимости может сразу примонтировать его.

Обычно команда управляет такими полями:

- source path
- VM name
- VM path
- backup path
- backup interval
- max backups
- cleanup policy
- allowed agents

## `removemount`

Удаляет mount entry из конфига. CLI сначала пытается размонтировать mount и сохраняет конфиг без изменений, если размонтирование не удалось.

## См. также

- [Конфигурация](../configuration.md)
- [Бэкапы](../backups.md)
- [run](run.md)
