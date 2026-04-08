# Agent Safety Kit

Хотите запускать Claude Code, Codex и других ИИ-агентов для разработки, но понимаете, чем это может закончиться на вашей рабочей машине?

Этот проект для тех, кто не хочет превращать собственный ноутбук в полигон для разрушительных экспериментов над кодом, секретами и цифровой безопасностью.

[Индекс документации](docs-ru/README.md) | [English docs](docs/README.md) | [Философия проекта](philosophy-ru.md)

## Почему это важно

То, как работают автономные ИИ-агенты, иногда действительно похоже на магию. Но это именно та магия, после которой у вас может исчезнуть проект, локальное окружение, база данных, приватные ключи и вообще всё, до чего агент сумеет дотянуться.

На сайтах как ИИ-гигантов, так и маленьких команд, пишущих собственных агентов, установка часто выглядит как безобидные `curl | bash`, `npm i -g ...` и затем `<agent_name>`. За этой простотой скрывается куда более неприятная формулировка: вы разрешаете выполнять недоверенный код на своей рабочей машине.

Несколько показательных историй и предупреждений:

- [ИИ-агент может съесть prompt injection и начать выполнять чужую волю на вашем ПК](https://arxiv.org/abs/2507.20526)
- [Claude Code обходит собственные защиты и сбегает из sandbox](https://ona.com/stories/how-claude-code-escapes-its-own-denylist-and-sandbox)
- [Qwen Coder agent destroys working builds](https://github.com/QwenLM/qwen-code/issues/354)
- [Codex keeps deleting unrelated and uncommitted files](https://github.com/openai/codex/issues/4969)
- [Claude Code deleted my entire workspace](https://www.reddit.com/r/ClaudeAI/comments/1m299f5/claude_code_deleted_my_entire_workspace_heres_the/)
- [I Asked Claude Code to Fix All Bugs, and It Deleted the Whole Repo](https://levelup.gitconnected.com/i-asked-claude-code-to-fix-all-bugs-and-it-deleted-the-whole-repo-e7f24f5390c5)

Везде пишут: «ну просто делай бэкапы», «ну просто используй git». Но этого мало:

- агенты уничтожают unstaged-изменения;
- агенты выходят за пределы папки проекта и своего sandbox и могут портить файлы в вашей ОС;
- агенты могут читать за пределами папки проекта и потенциально смогут прочитать и отправить ваши приватные SSH-ключи или другие секреты злоумышленнику, съев prompt injection где-нибудь на странице документации, в issue tracker или в заражённом проекте;
- агенты могут воспользоваться уязвимостями ядра или локального окружения, если вы дали им слишком много прав, инструментов и доверия;
- даже из лучших побуждений агент может нафантазировать несуществующую информацию, удалить «сломанный» проект вместо починки, уронить БД и снести её бэкапы, просто потому что уверенно выбрал неправильное действие.

Современные coding-агенты уже показывают очень высокий уровень на задачах, связанных с поиском и эксплуатацией уязвимостей. Если дать такому агенту широкий доступ, сеть и плохую цель, радиус последствий легко выйдет далеко за пределы одного репозитория. `agsekit` существует именно потому, что относиться к этому как к теории — легкомысленно.

## Архитектура

Placeholder: сюда будет вставлена схема архитектуры.

Базовый цикл работы такой:

- Хостовая машина хранит реальный исходный код и запускает Ubuntu VM через Multipass.
- Папка проекта монтируется с хоста в выбранную VM.
- Бинарник агента запускается внутри VM, а не на хосте.
- `agsekit` запускает повторяющиеся инкрементальные бэкапы смонтированной папки, пока идёт агентная сессия.
- Для ограниченных сетей доступны `proxychains`, `http_proxy` и `portforward`.

Подробности: [docs-ru/architecture.md](docs-ru/architecture.md)

## Демо

Placeholder: сюда будет вставлен GIF / screencast из терминала.

Подходящий сценарий для демо:

1. Сгенерировать конфиг.
2. Поднять VM через `agsekit up`.
3. Добавить mount.
4. Запустить агента через `agsekit run`.
5. Показать, как параллельно создаются backup snapshots.

## Быстрый старт

Установка:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install agsekit
```

Создание конфига:

```bash
agsekit config-gen
```

Подготовка окружения:

```bash
agsekit up
```

Добавление проекта как mount:

```bash
agsekit addmount /path/to/project
```

Запуск агента из директории проекта:

```bash
cd /path/to/project
agsekit run qwen
```

Подробный старт: [docs-ru/getting-started.md](docs-ru/getting-started.md)

## Возможности

- Запуск агентов внутри VM Multipass, а не напрямую на хосте.
- Декларативный YAML для VM, mount, сетевых настроек и agent defaults.
- Автоматические инкрементальные бэкапы со снапшотами на hardlink.
- Несколько виртуальных машин с привязкой конкретных агентов к конкретным VM, например чтобы разделять NDA-проекты, работу и хобби по разным средам и моделям.
- Установка поддерживаемых agent CLI в целевые VM через `install-agents`.
- Поддержка `proxychains` для установки и runtime.
- Поддержка `http_proxy` на уровне VM и агента.
- Поддержка постоянного SSH port forwarding через `agsekit portforward`.
- И интерактивные, и неинтерактивные сценарии CLI.
- Автоматическая подготовка Linux и macOS хостов.

## Документация

- [Индекс документации](docs-ru/README.md)
- [Быстрый старт](docs-ru/getting-started.md)
- [Практические how-to](docs-ru/how-to.md)
- [Архитектура](docs-ru/architecture.md)
- [Конфигурация](docs-ru/configuration.md)
- [Агенты](docs-ru/agents.md)
- [Сеть и прокси](docs-ru/networking.md)
- [Бэкапы](docs-ru/backups.md)
- [Справка по командам](docs-ru/commands/README.md)
- [Troubleshooting](docs-ru/troubleshooting.md)
- [Known issues](docs-ru/known-issues.md)

## Поддерживаемые агенты

- [aider](https://aider.chat/)
- [Qwen Code](https://qwenlm.github.io/qwen-code-docs/en/)
- [ForgeCode](https://forgecode.dev/)
- [Codex](https://openai.com/codex/)
- [OpenCode](https://opencode.ai/)
- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- [Cline](https://cline.bot/)
- `codex-glibc` — вариант [Codex](https://openai.com/codex/), собираемый внутри VM
- `codex-glibc-prebuilt` — вариант [Codex](https://openai.com/codex/), ставящийся из готового prebuilt-релиза

Подробности: [docs-ru/agents.md](docs-ru/agents.md)

## Модель безопасности и ограничения

Что инструмент делает:

- изолирует запуск агента внутри VM;
- держит хостовый проект в mounted storage;
- создаёт rollback-friendly backups вокруг агентных запусков.

Что инструмент не делает:

- не гарантирует безопасность sandbox внутри guest VM;
- не предотвращает плохие правки в смонтированном проекте;
- не заменяет code review, git hygiene и аккуратную работу с секретами.

Подробнее: [philosophy-ru.md](philosophy-ru.md)

## Поддержка платформ

- Linux host: поддерживается
- macOS host: поддерживается для Multipass-based workflow
- Windows host: пока не first-class workflow
- Guest OS: Ubuntu через Multipass

## FAQ

### Для кого это?

Для разработчиков, которые хотят пользоваться coding-агентами, но хотят изоляцию и точки отката.

### Нужен ли git?

Да. `agsekit` дополняет git, а не заменяет его.

### Почему Multipass, а не Docker?

Проект целится в workflow с полноценной Ubuntu VM, SSH, mount, port forwarding и установщиками агентов, которые ведут себя как обычная Linux-машина.

## Contributing и License

- Материалы для контрибьюторов будут развиваться в `docs/`.
- Лицензия: [LICENSE](LICENSE)
