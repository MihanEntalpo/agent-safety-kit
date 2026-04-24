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

По умолчанию install-agents использует proxychains из конфигурации ВМ, что можно переопределить при запуске. Сама runtime-инфраструктура proxychains/http-proxy готовится на уровне ВМ во время её подготовки, поэтому installer агента при необходимости только собирает временный proxychains config и command prefix:

- `--proxychains scheme://host:port` переопределяет VM proxy только для этой установки.
- `--proxychains ""` отключает proxy на один запуск.

## Примеры

```bash
agsekit install-agents qwen
agsekit install-agents qwen agent-ubuntu
agsekit install-agents --all-agents --all-vms
agsekit install-agents claude --debug
```

## Примечания

Для Node-based агентов (`codex`, `qwen`, `opencode`, `cline`), если `node` отсутствует, installer сначала резолвит через `nvm ls-remote` последнюю доступную patch-версию в поддерживаемой major-ветке Node 24 и ставит уже её точное значение.

Для тех же Node-based агентов installer проверяет уже установленный Node.js и в текущем `PATH`, и через `nvm use --silent default`, так что версия Node, уже установленная через `nvm`, не приводит к лишней переустановке только из-за того, что Ansible работает в non-login shell. Если в одном запуске `install-agents` несколько Node-based агентов ставятся в одну и ту же ВМ, `agsekit` после первого успешного installer run запоминает, что `nvm` и Node.js там уже готовы, и передаёт в следующие playbook дополнительные флаги для пропуска повторной подготовки `nvm`/Node.

Для `codex`, `codex-glibc` и `codex-glibc-prebuilt` installer также настраивает внутри VM `logrotate` для `~/.codex/log/codex-tui.log` с политикой `size 100M`, `rotate 10`, `compress`, `delaycompress`, `missingok`, `notifempty` и `copytruncate`.


## См. также

- [Агенты](../agents.md)
- [run](run.md)
- [Сеть](../networking.md)
