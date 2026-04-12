# Команды жизненного цикла VM

## Команды

## `start-vm`

Запускает выбранную VM или все настроенные VM.

```bash
agsekit start-vm <vm_name>|--all-vms [--config <path>] [--debug]
```

## `stop-vm`

Останавливает выбранную VM или все настроенные VM. Если это требуется текущей реализации, активные mount сначала размонтируются.

```bash
agsekit stop-vm <vm_name>|--all-vms [--config <path>] [--debug]
```

## `restart-vm`

Выполняет последовательность stop/start для выбранных целей.

```bash
agsekit restart-vm <vm_name>|--all-vms [--config <path>] [--debug]
```

## `down`

Останавливает все настроенные VM. Если настроенные агенты всё ещё работают, `agsekit` показывает их и просит подтверждение, если не передан `--force`.

На Linux `down` также пытается сначала остановить `portforward` systemd service.

```bash
agsekit down [--config <path>] [-f|--force] [--debug]
```

## `destroy-vm`

Удаляет VM из Multipass после подтверждения.

```bash
agsekit destroy-vm <vm_name>|--all [--config <path>] [-y] [--debug]
```

## См. также

- [create-vm](create-vm.md)
- [status](status.md)
