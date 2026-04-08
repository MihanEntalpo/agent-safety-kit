# Команды жизненного цикла VM

## Команды

```bash
agsekit start-vm <vm_name>|--all-vms [--config <path>] [--debug]
agsekit stop-vm <vm_name>|--all-vms [--config <path>] [--debug]
agsekit restart-vm <vm_name>|--all-vms [--config <path>] [--debug]
agsekit down [--config <path>] [-f|--force] [--debug]
agsekit destroy-vm <vm_name>|--all [--config <path>] [-y] [--debug]
```

## `start-vm`

Запускает выбранную VM или все настроенные VM.

## `stop-vm`

Останавливает выбранную VM или все настроенные VM. Если это требуется текущей реализации, активные mount сначала размонтируются.

## `restart-vm`

Выполняет последовательность stop/start для выбранных целей.

## `down`

Останавливает все настроенные VM. Если настроенные агенты всё ещё работают, `agsekit` показывает их и просит подтверждение, если не передан `--force`.

На Linux `down` также пытается сначала остановить `portforward` systemd service.

## `destroy-vm`

Удаляет VM из Multipass после подтверждения.

## См. также

- [create-vm](create-vm.md)
- [status](status.md)
