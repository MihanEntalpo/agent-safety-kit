# Поддерживаемые агенты

`agsekit` управляет установкой и runtime-запуском фиксированного набора agent types.

Агенты - это по сути бинарники от различных производителей, таких как claude-code, codex или cline.

## Поддерживаемые типы

- `aider` - [aider](https://aider.chat/)
- `qwen` - [Qwen Code](https://qwenlm.github.io/qwen-code-docs/en/)
- `forgecode` - [ForgeCode](https://forgecode.dev/)
- `codex` - [Codex](https://openai.com/codex/)
- `opencode` - [OpenCode](https://opencode.ai/)
- `claude` - [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- `cline` - [Cline](https://cline.bot/)
- `codex-glibc` - вариант [Codex](https://openai.com/codex/), собираемый внутри VM
- `codex-glibc-prebuilt` - вариант [Codex](https://openai.com/codex/), ставящийся из готового prebuilt-релиза

## Модель установки

Команда `install-agents` выбирает Ansible playbook для нужного типа и устанавливает соответствующий runtime в целевую VM.

Основные паттерны:

- npm CLI для `codex`, `qwen`, `opencode` и `cline`
- официальные установщики для `aider`, `forgecode` и `claude`
- локальная сборка из исходников для `codex-glibc`
- скачивание release asset для `codex-glibc-prebuilt`

## Модель запуска

`agsekit run` резолвит профиль агента, применяет default arguments, env, ограничения mount/VM и сетевые настройки, а затем запускает агента внутри VM.

## OpenAI-compatible API и другие настройки

Конкретные runtime flags зависят от CLI агента. Обычный паттерн такой:

1. добавить provider-specific default arguments в `agents.<name>.default-args`, `agents.<name>.env` или передавать их в runtime;
2. не хранить секреты в репозитории;
3. использовать те же provider-specific flags, что и без `agsekit`.

К сожалению, у всех агентов настройка делается полностью по-своему, поэтому искать, как подключить конкретный агент к конкретной сетке надо искать в их документации.

## Заметки

- runtime `forgecode` всегда получает `FORGE_TRACKER=false`, так как forgecode иначе отправит "для статистики" ваши данные, включая email и имя из .gitconfig
- `codex-glibc` и `codex-glibc-prebuilt` это отдельные бинарники и могут сосуществовать с `codex`.
- источник релизов для `codex-glibc-prebuilt` можно переопределить через host environment variables.

## См. также

- [install-agents](commands/install-agents.md)
- [run](commands/run.md)
- [Сеть](networking.md)
