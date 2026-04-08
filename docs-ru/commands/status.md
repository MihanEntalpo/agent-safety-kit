# `status`

## Назначение

Показать сводный operational report по настроенному окружению.

## Команда

```bash
agsekit status [--config <path>] [--debug]
```

## Что показывает

- путь к конфигу
- состояния VM
- настроенные и реальные ресурсы VM
- состояние процесса `portforward`
- информацию о mount и backup snapshots
- настроенных и установленных агентов по VM
- текущие agent processes и их рабочие директории

## Пример

```bash
agsekit status
agsekit status --debug
```

## См. также

- [run](run.md)
- [Жизненный цикл VM](vm-lifecycle.md)
- [Сетевые команды](networking.md)
