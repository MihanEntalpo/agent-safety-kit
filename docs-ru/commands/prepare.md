# `prepare`

## Назначение

Подготовить хостовую машину к workflow `agsekit`.

## Команда

```bash
agsekit prepare [--config <path>] [--debug]
```

## Что делает

- ставит нужные host-side зависимости, прежде всего Multipass;
- создаёт или повторно использует host SSH keypair для доступа к VM;
- читает `global.ssh_keys_folder` из конфига, если он доступен.

## Замечания по платформам

- Linux: поддерживаются Debian-based и Arch-based установки пакетов.
- macOS: Multipass ставится через Homebrew.
- Windows: пока не является first-class workflow.

## Примеры

```bash
agsekit prepare
agsekit prepare --debug
agsekit prepare --config ~/.config/agsekit/config.yaml
```

## См. также

- [up](up.md)
- [Конфигурация](../configuration.md)
