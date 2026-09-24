# `install-agents`

## Содержание

- [Назначение](#назначение)
- [Команды](#команды)
- [Правила выбора целей](#правила-выбора-целей)
- [Переопределение proxychains](#переопределение-proxychains)
- [Примеры](#примеры)

## Назначение

Установить один или несколько настроенных agent runtime в одну или несколько VM.

Перед запуском installer playbook `agsekit` проверяет, что в VM добавлен host SSH key. Bootstrap ключа выполняется через Multipass. На Linux и macOS сам installer запускается через Ansible по SSH с ключом из `global.ssh_keys_folder`, а на native Windows PowerShell он запускается внутри целевой ВМ против `localhost` через VM-local control node.

Версия агента берётся из `agents.<name>.version`. Если поле не задано, `agsekit` ставит последнюю upstream-версию без фиксации. Значение `stable` выбирает проверенную версию agsekit, а semver-строка фиксирует точную версию.

## Команды

```bash
agsekit install-agents <agent_name> [<vm>|--all-vms] [--upgrade [--force-check-versions]] [--config <path>] [--proxychains <value>] [--debug]
agsekit install-agents --all-agents [--all-vms] [--upgrade [--force-check-versions]] [--config <path>] [--proxychains <value>] [--debug]
```

## Правила выбора целей

- Если `<vm>` не передана, `agsekit` использует целевую VM агента из конфига.
- Если у агента нет ограничений по VM, целями становятся все VM из конфига.
- При `--all-vms` все VM выбираются явно.

## Переопределение proxychains

По умолчанию install-agents использует proxychains из конфигурации ВМ, что можно переопределить при запуске. Сама runtime-инфраструктура proxychains/http-proxy готовится на уровне ВМ во время её подготовки, поэтому installer агента при необходимости только собирает временный proxychains config и command prefix:

- `--proxychains scheme://host:port` переопределяет VM proxy только для этой установки.
- `--proxychains ""` отключает proxy на один запуск.

## Примеры

```bash
agsekit install-agents qwen
agsekit install-agents qwen agent-ubuntu
agsekit install-agents --all-agents --all-vms
agsekit install-agents --all-agents --upgrade
agsekit install-agents codex --upgrade --force-check-versions
agsekit install-agents claude --debug
```

## Примечания

Перед запуском playbook `agsekit` спрашивает у уже существующего бинарника его версию. Если она уже совпадает с требуемой, шаг установки пропускается. Если бинарник есть, но версия отличается, `agsekit` переустанавливает агента до версии, объявленной в конфиге.

С флагом `--upgrade` версия из конфига временно заменяется последней версией типа агента, сохранённой в `state.yaml`. Сама команда не обращается к npm, PyPI или GitHub; если кэш ещё не заполнен, сначала нужно выполнить `agsekit check-new-version`. Совпадающая установленная версия пропускается, а более старая или просто отличающаяся переустанавливается. YAML-конфиг не изменяется.

`--force-check-versions` можно использовать только вместе с `--upgrade`. Флаг игнорирует 24-часовой кэш для выбранных уникальных типов агентов, немедленно опрашивает их upstream-источники, записывает успешные результаты в `state.yaml`, а затем устанавливает только что найденные версии. Если хотя бы один выбранный тип не удалось обновить, установка останавливается и не использует его устаревшее cached-значение.

Для Node-based агентов (`codex`, `qwen`, `opencode`, `claude`, `cline`), если `node` отсутствует, installer сначала резолвит текущую LTS-версию Node.js через `nvm version-remote --lts` и ставит именно её точное значение. Если Node.js уже найден, installer сохраняет существующую версию и не обновляет её автоматически только потому, что появилась более новая LTS.

Для тех же Node-based агентов installer проверяет уже установленный Node.js и в текущем `PATH`, и через `nvm use --silent default`, так что версия Node, уже установленная через `nvm`, не приводит к лишней переустановке только из-за того, что Ansible работает в non-login shell. Если в одном запуске `install-agents` несколько Node-based агентов ставятся в одну и ту же ВМ, `agsekit` после первого успешного installer run запоминает, что `nvm` и Node.js там уже готовы, и передаёт в следующие playbook дополнительные флаги для пропуска повторной подготовки `nvm`/Node.

Для `codex-glibc-prebuilt` agsekit резолвит точный GitHub release tag, соответствующий запрошенной версии. Для `codex-glibc` перед сборкой клонируется точный matching Git tag.

Оба installer'а `codex-glibc` также скачивают официальный release asset `codex-code-mode-host` той же версии, если он опубликован для этого релиза, и устанавливают его рядом с основным бинарником. Новым версиям Codex этот helper нужен для tool-вызовов и файловых операций в Code Mode; upstream MUSL-сборку можно использовать без изменений, ей не требуется glibc/proxy-пересборка основного бинарника. Старые релизы без такого asset остаются устанавливаемыми.

Для зафиксированной версии, которой нет в upstream, установка завершается явной ошибкой, а не молча скатывается на `latest`.

Для `codex`, `codex-glibc` и `codex-glibc-prebuilt` installer также настраивает внутри VM `logrotate` для `~/.codex/log/codex-tui.log` с политикой `size 100M`, `rotate 10`, `compress`, `delaycompress`, `missingok`, `notifempty` и `copytruncate`.


## См. также

- [Агенты](../agents.md)
- [run](run.md)
- [Сеть](../networking.md)
