# `prepare`

## Содержание

- [Назначение](#назначение)
- [Команда](#команда)
- [Что делает](#что-делает)
- [Замечания по платформам](#замечания-по-платформам)
- [Примеры](#примеры)

## Назначение

Подготовить хостовую машину к workflow `agsekit`.

## Команда

```bash
agsekit prepare [--config <path>] [--debug]
```

## Что делает

- проверяет нужные host-side зависимости;
- если `multipass` уже есть в `PATH`, не ставит ни Multipass, ни `snapd`;
- если нужны host-пакеты, ставит только отсутствующие;
- проверяет наличие `ssh-keygen` и при необходимости ставит OpenSSH client package на поддерживаемом Linux;
- проверяет наличие `rsync` и при необходимости ставит его через пакетный менеджер Linux или через Homebrew на macOS;
- создаёт или повторно использует host SSH keypair для доступа к VM;

## Замечания по платформам

- Linux: поддерживаются Debian-based и Arch-based установки пакетов; на Debian-based `snapd` ставится только если отсутствует `multipass`
- macOS: Multipass и `rsync` ставятся через Homebrew, только если отсутствуют.
- Windows host: пока только через WSL.
- WSL: `prepare` не ставит `snapd` и Multipass внутри WSL; Multipass должен быть установлен в Windows и доступен как команда `multipass` внутри WSL.

## Примеры

```bash
agsekit prepare
agsekit prepare --debug
agsekit prepare --config ~/.config/agsekit/config.yaml
```

## См. также

- [up](up.md)
- [Конфигурация](../configuration.md)
