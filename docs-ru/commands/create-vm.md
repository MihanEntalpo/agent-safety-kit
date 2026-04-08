# `create-vm` и `create-vms`

## Назначение

Создавать VM Multipass из конфига и готовить их к работе агентов.

## Команды

```bash
agsekit create-vm <name> [--config <path>] [--debug]
agsekit create-vms [--config <path>] [--debug]
```

## Что происходит

- `agsekit` проверяет, существует ли VM;
- запускает отсутствующие VM с нужными ресурсами;
- стартует VM;
- синхронизирует SSH-доступ;
- ставит базовые пакеты через Ansible.

## Поведение для уже существующей VM

Если VM уже есть, `agsekit` сравнивает реальные и настроенные ресурсы и сообщает о различиях. Автоматическое изменение размеров существующей VM пока не поддерживается.

## Примеры

```bash
agsekit create-vms
agsekit create-vm agent-ubuntu
agsekit create-vm agent-ubuntu --debug
```

## См. также

- [prepare](prepare.md)
- [Жизненный цикл VM](vm-lifecycle.md)
- [Конфигурация](../configuration.md)
