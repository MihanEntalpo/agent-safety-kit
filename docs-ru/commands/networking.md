# Сетевые команды

## Команды

## `portforward`

```bash
agsekit portforward [--config <path>] [--debug]
```

Поддерживает настроенные SSH tunnels и периодически перечитывает конфиг, чтобы адаптироваться к изменениям forwarding rules.

## `ssh`

```shell
agsekit ssh <vm_name> [--config <path>] [--debug] [<ssh_args...>]
```

Подключается к VM по SSH, используя host-side key, которым управляет `agsekit`.

Позволяет передавать произвольные ssh-ключи, как в обычную команду ssh.

Типовые применения:

- ручная отладка;
- ad-hoc выполнение команд;
- дополнительные forwards через `-L`, `-R` и `-N`.

## `shell`

```
agsekit shell [<vm_name>] [--config <path>] [--debug]
```

Открывает интерактивную `multipass shell` сессию в выбранной VM, по сути работает так же через ssh, но использует ключи multipass, и не позволяет передавать стандартные ssh-аргументы

## См. также

- [Сеть и прокси](../networking.md)
- [systemd](systemd.md)
