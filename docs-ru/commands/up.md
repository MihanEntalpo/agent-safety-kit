# `up`

## Содержание

- [Назначение](#назначение)
- [Команда](#команда)
- [Что делает](#что-делает)
- [Заметки](#заметки)
- [Примеры](#примеры)

## Назначение

Запустить основной bootstrap flow без интерактивных вопросов.

## Команда

```bash
agsekit up [--config <path>] [--debug] [--prepare/--no-prepare] [--create-vms/--no-create-vms] [--install-agents/--no-install-agents]
```

## Что делает

В зависимости от флагов `up` может:

- подготовить хост;
- создать и подготовить все настроенные VM;
- установить всех настроенных агентов в их целевые VM;
- на поддерживаемых платформах установить или обновить daemon для фоновых сервисов, включая `portforward`.

По сути, это аналог поочерёдного запуска команд: `agsekit prepare`, `agsekit create-vms`, `agsekit install-agents`, `agsekit daemon install`

По умолчанию все 4 и запускаются.

## Заметки

- Хотя бы один этап должен остаться включённым.
- Если для workflow нужен конфиг и он не найден, команда падает.

## Примеры

```bash
agsekit up
agsekit up --debug
agsekit up --no-prepare
agsekit up --prepare --no-create-vms --no-install-agents
```

## См. также

- [prepare](prepare.md)
- [create-vm / create-vms](create-vm.md)
- [install-agents](install-agents.md)
- [daemon](daemon.md)
