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

## Замечания по платформам

- Linux: поддерживаются Debian-based и Arch-based установки пакетов, использует snapd
- macOS: Multipass ставится через Homebrew.
- Windows: пока не является first-class workflow, поэтому multipass здесь нужно ставить вручную

## Примеры

```bash
agsekit prepare
agsekit prepare --debug
agsekit prepare --config ~/.config/agsekit/config.yaml
```

## См. также

- [up](up.md)
- [Конфигурация](../configuration.md)
