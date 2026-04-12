# `run`

## Назначение

Запустить агента внутри целевой VM, сохраняя проект на хосте в mounted виде делая параллельные бэкапы.

## Команда

В простейшей форме:

```shell
agsekit run <agent_name>
```

Со всеми аргументами:

```bash
agsekit run [--vm <vm_name>] [--config <path>] [--workdir <path>] [--proxychains <value>] [--http-proxy <value>] [--disable-backups] [--auto-mount] [--skip-default-args] [--debug] <agent_name> [<agent_args...>]
```

## Важное правило разбора аргументов

Все опции `agsekit run` должны стоять до `<agent_name>`. Всё, что идёт после `<agent_name>`, передаётся самому агенту без изменений.

В результате, если вы ранее пользовались агентом без agsekit, то перейти на agsekit будет не сложно.

Там где было `claude auth login` теперь будет `agsekit run claude auth login`

## Правила workdir

- по умолчанию workdir это текущая директория на хосте;
- `--workdir` может указывать на другую настроенную mount path;
- если выбранная директория существует и соответствует mount из конфига, `run` стартует в соответствующем пути внутри VM;
- если это вложенная поддиректория, внутри VM сохраняется тот же относительный подпуть.
- если выбранная директория не существует в интерактивном терминале, `run` спрашивает, запустить ли агента во временной директории внутри VM (`/tmp/run-*`); в этом режиме host mount не используется и бэкапы не запускаются.
- если выбранная директория существует, но не входит в настроенные mount, интерактивный режим предлагает тот же fallback на временную директорию внутри VM (`/tmp/run-*`).
- в non-interactive режиме отсутствующая workdir, либо запуск вне настроенных mount-папок считается ошибкой.

## Проверки mount

- если подходящий mount найден, но ещё не примонтирован в Multipass, `run` может примонтировать его перед запуском;
- `--auto-mount` делает это автоматически;
- когда выбранный mount уже активен (папка примонтирована), `run` предупреждает, если папка на хосте непустая, 
а соответствующий путь внутри VM пуст, это обычно свидетельствует о сбое multipass, и требует вызова `agsekit doctor`

## Runtime helper'ы

`run` также умеет:

- автоматически монтировать исходную директорию через `--auto-mount`;
- НЕ запускать repeated backups, если передан `--disable-backups`;
- применять agent default arguments, если не передан `--skip-default-args`;
- оборачивать runtime через `proxychains` или `http_proxy`;
- переопределять `proxychains` через `--proxychains <scheme://host:port>` или отключать его через `--proxychains ""`;
- переопределять `http_proxy` в upstream-режиме через `--http-proxy <scheme://host:port>` или отключать его через `--http-proxy ""`.

## Ограничения

Права на запуск агента проверяются в таком порядке:

1. Сначала `mounts[].allowed_agents`
2. Затем `vms.<vm>.allowed_agents`
3. И если ни там ни там не встретилось проблем - агент запускается

## Примеры

```bash
cd /path/to/project
agsekit run qwen
agsekit run claude auth login
agsekit run --vm agent-ubuntu codex --sandbox danger-full-access
agsekit run --workdir /path/to/project/subdir qwen
agsekit run --auto-mount --proxychains socks5://127.0.0.1:1080 qwen
agsekit run --http-proxy socks5://127.0.0.1:8181 qwen
```

## См. также

- [Агенты](../agents.md)
- [Сеть](../networking.md)
- [Бэкапы](../backups.md)
