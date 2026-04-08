# `systemd`

## Назначение

Управлять Linux-only user service, который держит `agsekit portforward` в фоне.

## Команды

```bash
agsekit systemd install [--config <path>] [--debug]
agsekit systemd uninstall [--debug]
agsekit systemd start [--debug]
agsekit systemd stop [--debug]
agsekit systemd restart [--debug]
agsekit systemd status [--debug]
```

## Поддержка платформ

- Linux: реализовано
- macOS: команда печатает предупреждение и ничего не делает
- Windows: команда печатает предупреждение и ничего не делает

## `install`

Записывает `systemd.env`, линкует bundled user unit, делает reload systemd, перезапускает сервис и включает его.

## `status`

Показывает:

- путь к bundled unit
- путь к linked user unit
- состояние установки
- active/enabled state
- хвост последних записей журнала

## Связь с `up`

На Linux `agsekit up` может автоматически установить или обновить этот сервис после этапов VM и agent setup.

## См. также

- [up](up.md)
- [Сетевые команды](networking.md)
