# `daemon`

## Содержание

- [Назначение](#назначение)
- [Команды](#команды)
- [Поддержка платформ](#поддержка-платформ)
- [`install`](#install)
- [`status`](#status)
- [Связь с `up` и `down`](#связь-с-up-и-down)
- [Устаревший alias](#устаревший-alias)

## Назначение

Управлять фоновыми сервисами, включая сервис, который держит `agsekit portforward` запущенным.

Backend по платформам:

- Linux: user-level `systemd`
- macOS: user-level `launchd`
- Windows: пока не реализовано

## Команды

```bash
agsekit daemon install [--config <path>] [--debug]
agsekit daemon uninstall [--debug]
agsekit daemon start [--debug]
agsekit daemon stop [--debug]
agsekit daemon restart [--debug]
agsekit daemon status [--debug]
```

## Поддержка платформ

- Linux: реализовано через `systemd`
- macOS: реализовано через `launchd`
- Windows: команда печатает предупреждение и ничего не делает

## `install`

Записывает конфигурацию демона для текущей платформы, регистрирует фоновые сервисы и запускает их.

На Linux:

- записывает `systemd.env`
- линкует bundled user unit
- делает reload `systemd`
- перезапускает и включает сервис

На macOS:

- записывает пользовательский `LaunchAgent`
- пишет логи демона в:
  - `~/Library/Logs/agsekit/daemon.stdout.log`
  - `~/Library/Logs/agsekit/daemon.stderr.log`
- выполняет bootstrap и запуск `launchd` job

В обоих случаях демон сохраняет абсолютный путь к текущему CLI `agsekit`, а `portforward` использует ту же установку и для дочерних `ssh`-процессов, не полагаясь на `PATH`.

## `status`

Вывод зависит от платформы.

На Linux показываются linked unit, состояние сервиса и последние строки `journalctl`.

На macOS показываются путь к plist, loaded/enabled state, PID, last exit status и хвост stdout/stderr логов.

## Связь с `up` и `down`

На поддерживаемых платформах `agsekit up` автоматически устанавливает или обновляет daemon после этапов подготовки VM и агентов.

`agsekit down` перед остановкой VM также пытается остановить сервисы, которыми управляет daemon.

## Устаревший alias

`agsekit systemd ...` остаётся доступным как устаревший alias. Он печатает предупреждение и затем запускает соответствующую команду `agsekit daemon ...`.

## См. также

- [up](up.md)
- [Жизненный цикл VM](vm-lifecycle.md)
- [Сетевые команды](networking.md)
- [systemd](systemd.md)
