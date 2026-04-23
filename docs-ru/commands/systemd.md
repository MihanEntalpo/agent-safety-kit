# `systemd`

## Содержание

- [Назначение](#назначение)
- [Устаревший alias](#устаревший-alias)
- [Оговорки по платформам](#оговорки-по-платформам)

## Назначение

`systemd` теперь является устаревшим alias для [`daemon`](daemon.md).

## Устаревший alias

```bash
agsekit systemd install [--config <path>] [--debug]
agsekit systemd uninstall [--debug]
agsekit systemd start [--debug]
agsekit systemd stop [--debug]
agsekit systemd restart [--debug]
agsekit systemd status [--debug]
```

Каждая команда печатает предупреждение и затем запускает соответствующую `agsekit daemon ...`.

## Оговорки по платформам

- На Linux `agsekit daemon` использует `systemd`.
- На macOS `agsekit daemon` использует `launchd`.
- На Windows `agsekit daemon` пока не реализован.

## См. также

- [daemon](daemon.md)
- [up](up.md)
- [Сетевые команды](networking.md)
