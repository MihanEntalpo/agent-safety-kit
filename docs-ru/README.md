# Документация

В этой директории находится пользовательская документация `agsekit`.

## С чего начать

- [Быстрый старт](getting-started.md)
- [Конфигурация](configuration.md)
- [Поддерживаемые агенты](agents.md)
- [Архитектура](architecture.md)
- [Сеть и прокси](networking.md)
- [Бэкапы](backups.md)
- [Решение проблем](troubleshooting.md)
- [Практические how-to](how-to.md)
- [Известные проблемы и недоработки](known-issues.md)

## Справка по командам

- [Индекс команд](commands/README.md)
  - [prepare](commands/prepare.md)
  - [up](commands/up.md)
  - [create-vm / create-vms](commands/create-vm.md)
  - [install-agents](commands/install-agents.md)
  - [run](commands/run.md)
  - [mount / umount / addmount / removemount](commands/mount.md)
  - [status](commands/status.md)
  - [doctor](commands/doctor.md)
  - [systemd](commands/systemd.md)
  - [Жизненный цикл VM](commands/vm-lifecycle.md)
  - [Сетевые команды](commands/networking.md)
  - [Backup-команды](commands/backups.md)

## Языки

- [English documentation](../docs/README.md)

CLI по возможности использует системную локаль. Поведение можно переопределить через `AGSEKIT_LANG`, например `AGSEKIT_LANG=ru agsekit --help`.

## См. также

- [README-new-ru.md](../README-new-ru.md)
- [Философия проекта](../philosophy-ru.md)
