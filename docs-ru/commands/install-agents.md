# `install-agents`

## Содержание

- [Назначение](#назначение)
- [Команды](#команды)
- [Правила выбора целей](#правила-выбора-целей)
- [Переопределение proxychains](#переопределение-proxychains)
- [Примеры](#примеры)

## Назначение

Установить один или несколько настроенных agent runtime в одну или несколько VM.

## Команды

```bash
agsekit install-agents <agent_name> [<vm>|--all-vms] [--config <path>] [--proxychains <value>] [--debug]
agsekit install-agents --all-agents [--all-vms] [--config <path>] [--proxychains <value>] [--debug]
```

## Правила выбора целей

- Если `<vm>` не передана, `agsekit` использует целевую VM агента из конфига.
- Если у агента нет ограничений по VM, целями становятся все VM из конфига.
- При `--all-vms` все VM выбираются явно.

## Переопределение proxychains

По умолчанию install-agents использует proxychains из конфигурации ВМ, что можно переопределить при запуске:

- `--proxychains scheme://host:port` переопределяет VM proxy только для этой установки.
- `--proxychains ""` отключает proxy на один запуск.

## Примеры

```bash
agsekit install-agents qwen
agsekit install-agents qwen agent-ubuntu
agsekit install-agents --all-agents --all-vms
agsekit install-agents claude --debug
```

## См. также

- [Агенты](../agents.md)
- [run](run.md)
- [Сеть](../networking.md)
