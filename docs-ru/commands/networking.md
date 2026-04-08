# Сетевые команды

## Команды

```bash
agsekit portforward [--config <path>] [--debug]
agsekit ssh <vm_name> [--config <path>] [--debug] [<ssh_args...>]
agsekit shell [<vm_name>] [--config <path>] [--debug]
```

## `portforward`

Поддерживает настроенные SSH tunnels и периодически перечитывает конфиг, чтобы адаптироваться к изменениям forwarding rules.

## `ssh`

Подключается к VM по SSH, используя host-side key, которым управляет `agsekit`.

Типовые применения:

- ручная отладка;
- ad-hoc выполнение команд;
- дополнительные forwards через `-L`, `-R` и `-N`.

## `shell`

Открывает интерактивную `multipass shell` сессию в выбранной VM.

## См. также

- [Сеть и прокси](../networking.md)
- [systemd](systemd.md)
