# Поддерживаемые агенты

`agsekit` управляет установкой и runtime-запуском фиксированного набора agent types.

## Поддерживаемые типы

- `aider`
- `qwen`
- `forgecode`
- `codex`
- `opencode`
- `claude`
- `cline`
- `codex-glibc`
- `codex-glibc-prebuilt`

## Модель установки

Команда `install-agents` выбирает Ansible playbook для нужного типа и устанавливает соответствующий runtime в целевую VM.

Основные паттерны:

- npm CLI для `codex`, `qwen`, `opencode` и `cline`
- официальные установщики для `aider`, `forgecode` и `claude`
- локальная сборка из исходников для `codex-glibc`
- скачивание release asset для `codex-glibc-prebuilt`

## Модель запуска

`agsekit run` резолвит профиль агента, применяет default arguments, ограничения mount/VM и сетевые настройки, а затем запускает агента внутри VM.

## OpenAI-compatible API

Конкретные runtime flags зависят от CLI агента. Обычный паттерн такой:

1. добавить provider-specific default arguments в `agents.<name>.default-args` или передавать их в runtime;
2. не хранить секреты в репозитории;
3. использовать те же provider-specific flags, что и без `agsekit`.

## Заметки

- runtime `forgecode` всегда получает `FORGE_TRACKER=false`.
- `codex-glibc` и `codex-glibc-prebuilt` это отдельные бинарники и могут сосуществовать с `codex`.
- источник релизов для `codex-glibc-prebuilt` можно переопределить через host environment variables.

## См. также

- [install-agents](commands/install-agents.md)
- [run](commands/run.md)
- [Сеть](networking.md)
