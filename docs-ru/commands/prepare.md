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
- проверяет наличие `rsync` и при необходимости ставит его через пакетный менеджер Linux, Homebrew на macOS или MSYS2 на native Windows;
- на native Windows, если MSYS2-утилит нет, спрашивает перед установкой MSYS2 через `winget` и `rsync`/`openssh` через MSYS2 `pacman`; ответ по умолчанию - yes;
- добавляет каталог бинарников MSYS2 в текущий процесс и пользовательский `PATH` на native Windows;
- создаёт или повторно использует host SSH keypair для доступа к VM;

## Замечания по платформам

- Linux: поддерживаются Debian-based и Arch-based установки пакетов; на Debian-based `snapd` ставится только если отсутствует `multipass`
- macOS: Multipass и `rsync` ставятся через Homebrew, только если отсутствуют. На macOS 13+ `prepare` ставит текущую cask Multipass; на macOS <13 ставит зафиксированную legacy cask Multipass 1.14.1.
- Windows host: native Windows может подготовить MSYS2 host-утилиты (`rsync` и `openssh`); Multipass for Windows нужно установить отдельно.
- WSL не поддерживается. Используйте обычный Linux-хост или native Windows PowerShell.

## Примеры

```bash
agsekit prepare
agsekit prepare --debug
agsekit prepare --config ~/.config/agsekit/config.yaml
```

## См. также

- [up](up.md)
- [Конфигурация](../configuration.md)
