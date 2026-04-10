# `run`

## Назначение

Запустить агента внутри целевой VM, сохраняя проект на хосте в mounted виде и при необходимости делая параллельные бэкапы.

## Команда

```bash
agsekit run [--vm <vm_name>] [--config <path>] [--workdir <path>] [--proxychains <value>] [--disable-backups] [--auto-mount] [--skip-default-args] [--debug] <agent_name> [<agent_args...>]
```

## Важное правило разбора аргументов

Все опции `agsekit run` должны стоять до `<agent_name>`. Всё, что идёт после `<agent_name>`, передаётся самому агенту без изменений.

## Правила workdir

- по умолчанию workdir это текущая директория на хосте;
- `--workdir` может указывать на другую настроенную mount path;
- если выбранная директория существует и соответствует mount из конфига, `run` стартует в соответствующем пути внутри VM;
- если это вложенная поддиректория, внутри VM сохраняется тот же относительный подпуть.
- если выбранная директория не существует в интерактивном терминале, `run` спрашивает, запустить ли агента во временной директории внутри VM (`/tmp/run-*`); в этом режиме host mount не используется и бэкапы не запускаются.
- если выбранная директория существует, но не входит в настроенные mount, интерактивный режим предлагает тот же fallback на временную директорию внутри VM (`/tmp/run-*`).
- в non-interactive режиме отсутствующая workdir по-прежнему считается ошибкой.
- в non-interactive режиме директория вне настроенных mount тоже остаётся ошибкой.

## Проверки mount

- если подходящий mount найден, но ещё не примонтирован в Multipass, `run` может примонтировать его перед запуском;
- `--auto-mount` делает это автоматически;
- когда выбранный mount уже активен, `run` предупреждает, если папка на хосте непустая, а соответствующий путь внутри VM пуст.

## Runtime helper'ы

`run` также умеет:

- автоматически монтировать исходную директорию через `--auto-mount`;
- запускать repeated backups, если не передан `--disable-backups`;
- применять agent default arguments, если не передан `--skip-default-args`;
- оборачивать runtime через `proxychains` или `http_proxy`.

## Ограничения

Права на запуск агента проверяются в таком порядке:

1. `mounts[].allowed_agents`
2. `vms.<vm>.allowed_agents`
3. без ограничений

## Примеры

```bash
cd /path/to/project
agsekit run qwen
agsekit run --vm agent-ubuntu codex --sandbox danger-full-access
agsekit run --workdir /path/to/project/subdir qwen
agsekit run --auto-mount --proxychains socks5://127.0.0.1:1080 qwen
```

## См. также

- [Агенты](../agents.md)
- [Сеть](../networking.md)
- [Бэкапы](../backups.md)
