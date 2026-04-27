# SPEC: Agent Safety Kit (`agsekit`)

Философская рамка проекта вынесена в отдельные документы:
- `docs-ru/philosophy.md` (русский)
- `docs/philosophy.md` (English)

Этот `SPEC.md` описывает текущее техническое состояние реализации и связывает его с целевой философией.

## 1. Продукт: зачем он нужен

`Agent Safety Kit` — это CLI-инструмент для безопасной работы с консольными AI-агентами (`aider`, `qwen`, `forgecode`, `codex`, `opencode`, `claude`, `cline`, `codex-glibc`, `codex-glibc-prebuilt`) через изоляцию в Multipass VM и регулярные инкрементальные бэкапы на хосте.

Ключевая пользовательская проблема:
- агент может повредить проект (удалить файлы, сломать рабочую копию, внести нежелательные изменения);
- стандартные «sandbox» режимы агентов часто недостаточны;
- пользователю нужен воспроизводимый, управляемый workflow с откатом и минимальной ручной рутины.

Основная идея решения:
- агент всегда исполняется внутри VM;
- рабочая папка проекта монтируется в VM;
- на хосте автоматически создаются снапшоты (`rsync` + `--link-dest`) в отдельной backup-папке;
- VM, mounts и агенты описаны в YAML-конфиге;
- вся операционная рутина (подготовка, создание VM, установка агентов, запуск, backup cleanup) сведена в одну CLI.

Принятое threat-model допущение:
- агент по умолчанию считается потенциально опасным (вероятностное поведение, а не гарантированно безопасная логика);
- безопасность должна обеспечиваться архитектурными ограничениями (изоляция + лимиты + бэкапы), а не доверием к агенту.

## 2. Для кого и какие user stories закрывает

Целевая аудитория:
- обычные разработчики, использующие консольных AI-агентов в реальных проектах;
- команды, где важно быстро восстановиться после неудачного прогона агента;
- энтузиасты и пользователи, которым нужна «инженерная» дисциплина запуска агентов без погружения в сложный DevOps/tooling.

Типовые user stories:
1. Как пользователь, я хочу один раз подготовить окружение (`prepare`, `create-vms`, `mount`) и дальше запускать агента одной командой.
2. Как пользователь, я хочу, чтобы при запуске агента автоматически работали фоновые бэкапы и не требовали ручного контроля.
3. Как пользователь, я хочу хранить инфраструктуру в YAML, чтобы конфигурация была воспроизводимой, переносимой и версионируемой.
4. Как пользователь, я хочу устанавливать окружение в VM декларативно (`install` bundles), чтобы не дублировать shell-скрипты.
5. Как пользователь, я хочу интерактивный режим для редких операций, но полноценный non-interactive режим для автоматизации.
6. Как пользователь, я хочу быстро управлять жизненным циклом VM и туннелями (`start/stop/destroy`, `portforward`, `daemon`).

## 3. Границы ответственности (что инструмент делает и чего не делает)

Инструмент делает:
- оркестрацию VM через Multipass;
- монтирование директорий и запуск агентов внутри VM;
- snapshot-like резервные копии на хосте;
- установку базовых пакетов/агентов через Ansible;
- управление локальным daemon-сервисом port-forwarding через `systemd` на Linux и `launchd` на macOS;

Инструмент не делает:
- не обеспечивает криптографическую защиту данных и не заменяет полноценный секрет-менеджмент;
- не «лечит» уязвимости самих AI-агентов;
- не меняет ресурсы уже существующей VM (только сообщает mismatch);
- не заменяет Git/remote backups (это локальный operational safety слой).

## 4. Архитектурные решения и rationale

### 4.1 Почему VM-first, а не container-first
- контейнеры делят ядро хоста, поэтому baseline-изоляция слабее, чем у полноценной VM;
- агентный workload часто сам должен работать с Docker (собирать образы, запускать compose/сервисы);
- запуск Docker внутри «защитного» контейнера обычно приводит к ослаблению изоляции (privileged mode или проброс docker socket);
- VM позволяет сохранить и изоляцию, и валидный DevOps-сценарий «контейнеры как целевая среда разработки».

### 4.2 Почему Multipass
- минимальный порог входа для Ubuntu VM;
- простые команды (`launch`, `exec`, `mount`, `info`);
- достаточно для изоляции агентного процесса от хоста;
- хорошо сочетается с Ansible: первичный bootstrap SSH-доступа выполняется через встроенный connection plugin `agsekit_multipass`, а дальнейшие playbook'и идут через стандартный Ansible SSH transport.

### 4.3 Почему бэкапы на хосте, а не «снэпшоты VM»
- целевой объект защиты — проектные файлы на хосте;
- backup-цепочка хранится рядом с проектом и легко восстанавливается;
- hardlink-инкременты экономят место;
- можно чистить историю гибкими политиками (`tail`/`thin`).

### 4.4 Почему YAML-конфиг
- единый источник правды для VM/mount/agent;
- удобно ревьюить, хранить в репозитории и переносить между машинами;
- CLI поддерживает явное разрешение пути (`--config`/`CONFIG_PATH`/default path).

### 4.5 Почему Ansible для установки ПО
- идемпотентность и воспроизводимость;
- декларативный слой над ручными shell-командами;
- простой путь расширять install bundles и agent installers.

### 4.6 Почему интерактивный fallback
- снижает порог входа для «ручного» пользователя;
- при этом не ломает автоматизацию (флаг `--non-interactive` полностью отключает prompts);
- команда без аргументов превращается в guided menu, а не в «глухую» ошибку.
- если команда требует конфиг, но кроме конфига у неё нет других обязательных параметров, отсутствие config-файла не уводит в TUI выбора конфига: CLI сразу печатает прямую ошибку о missing config;
- интерактивный выбор пути к конфигу сохраняется только для команд, которым при этом обычно не хватает и других обязательных пользовательских параметров.

## 5. Компоненты системы

- `agsekit_cli/cli.py`
  - регистрация команд;
  - логика интерактивного fallback;
  - глобальный вход `main()`.
- `agsekit_cli/config.py`
  - загрузка YAML;
  - dataclass-модели (`VmConfig`, `MountConfig`, `AgentConfig`, `PortForwardingRule`);
  - валидация/нормализация.
- `agsekit_cli/vm.py`
  - проверка Multipass;
  - сравнение существующих VM и проверка ресурсов хоста;
  - запуск VM;
  - optional `multipass launch --timeout` через env `AGSEKIT_MULTIPASS_LAUNCH_TIMEOUT_SECONDS` (если переменная не задана, extra timeout не добавляется);
  - port-forward аргументы;
  - резолв proxychains override и пути раннеров.
- `agsekit_cli/vm_prepare.py`
  - host SSH keypair;
  - host-side helper'ы подготовки VM для Linux/macOS (fetch VM info, host-side Ansible SSH transport, bundles).
- `agsekit_cli/vm_ssh_bootstrap.py`
  - host-side bootstrap SSH-доступа в VM через `multipass exec`;
  - обновление `authorized_keys` и локального `known_hosts` без Ansible control node на хосте.
- `agsekit_cli/vm_local_control_node.py`
  - подготовка persistent VM-local control node внутри гостевой Ubuntu VM;
  - копирование automation payload, создание guest venv и запуск `ansible-playbook` внутри VM против `localhost`.
- `agsekit_cli/provision_handlers.py`
  - platform-specific provisioning handler factory;
  - Linux/macOS используют host-side Ansible over SSH; native Windows использует VM-local Ansible control node.
- `agsekit_cli/mounts.py`
  - mount/umount wrappers;
  - поиск mount по пути (longest-prefix).
- `agsekit_cli/backup.py`
  - one-off/repeated backup;
  - cleanup (`tail`, `thin`);
  - `.backupignore` parsing;
  - progress bar;
  - `.inodes` manifest.
- `agsekit_cli/agents.py`
  - выбор mount/VM;
  - orchestration поверх agent modules;
  - merge `default-args` и user args;
  - запуск фонового backup-процесса.
- `agsekit_cli/agents_modules/*`
  - базовый `BaseAgent` и отдельные классы по типам агентов (`AiderAgent`, `QwenAgent`, `ForgecodeAgent`, `CodexAgent`, ...);
  - единый registry поддерживаемых agent types;
  - agent-specific логика `needs_nvm`, `build_shell_command`, `build_env` и другие runtime-особенности.
- `agsekit_cli/commands/*`
  - user-facing команды Click.
- `agsekit_cli/ansible/*`
  - playbooks для базовой подготовки VM, install bundles, установки агентов.

## 6. Конфигурационная модель

### 6.1 Где ищется конфиг
Порядок резолва:
1. `--config <path>`
2. `CONFIG_PATH`
3. `~/.config/agsekit/config.yaml`

### 6.2 Верхнеуровневые секции
- `global` — глобальные настройки agsekit;
- `vms` — описание виртуальных машин;
- `mounts` — описание монтируемых директорий и backup-политики;
- `agents` — описание агентных профилей запуска.

### 6.3 Секция `global`
Поля:
- `ssh_keys_folder` (optional, default `~/.config/agsekit/ssh`) — каталог с SSH-ключами хоста, используемыми для доступа к VM.
  - используется в `prepare`, `create-vm`, `create-vms`, `install-agents`, `ssh`, `portforward` и post-bootstrap Ansible-запусках;
  - при значении `null` или отсутствии поля берётся путь по умолчанию.
- `systemd_env_folder` (optional, default `~/.config/agsekit`) — каталог, куда записывается `systemd.env` для Linux backend команды `daemon`.
  - используется в `daemon install` и `up` только на Linux;
  - текущий systemd unit по-прежнему читает `~/.config/agsekit/systemd.env`, поэтому при кастомном каталоге CLI создаёт compatibility symlink из стандартного пути на фактический env-файл.
- `portforward_config_check_interval_sec` (optional, default `10`, >0) — интервал перечитывания YAML-конфига командой `portforward`.
  - применяется и при ручном запуске `agsekit portforward`, и в daemon-режиме, потому что backend запускает ту же CLI-команду.
- `http_proxy_port_pool.start` / `http_proxy_port_pool.end` (optional, defaults `48000..49000`) — диапазон auto-port для временного локального HTTP proxy helper внутри VM.
  - используется только в `run`, когда effective `http_proxy` задан в upstream-режиме и `listen` явно не указан.

### 6.4 Секция `vms`
Каждая VM:
- `cpu` (обязателен) — число vCPU (положительное целое).
- `ram` (обязателен) — объём RAM (строка/число, например `4G`, `4096M`).
- `disk` (обязателен) — размер диска (строка/число).
- `cloud-init` (optional) — cloud-init mapping, передается в `multipass launch --cloud-init`.
- `proxychains` (optional) — URL прокси `scheme://host:port`.
  - допустимые схемы: `http`, `https`, `socks4`, `socks5`;
  - user/pass/path/query/fragment не допускаются.
- `http_proxy` (optional) — настройка HTTP proxy для `run`.
  - поддерживаются формы:
    - shorthand string `scheme://host:port` => upstream-режим через временный `privoxy`;
    - mapping `{ upstream: scheme://host:port, listen?: host:port|port }`;
    - mapping `{ url: http://host:port }` для прямого режима без `privoxy`.
  - bare `listen` port нормализуется в `127.0.0.1:<port>`.
  - `url` и `upstream` взаимоисключающие.
  - `listen` допустим только вместе с `upstream`.
- `port-forwarding` (optional) — список правил проброса портов.
  - `type=local`: открыть порт на хосте и пробросить в VM (`ssh -L host:vm`).
  - `type=remote`: открыть порт в VM и пробросить на хост (`ssh -R vm:host`).
  - `type=socks5`: поднять SOCKS5-порт в VM (`ssh -D vm`).
- `install` (optional) — список install bundles (`python`, `nodejs:20`, `docker`, ...), которые выполняются на этапе `create-vm/create-vms`.
- `allowed_agents` (optional) — список имён агентов из секции `agents` или строка имён, разделённых запятыми.
  - если поле задано, `run` в этой VM разрешён только для перечисленных агентов в случаях, когда mount-ограничение не задано;
  - если поле отсутствует, для VM ограничение не применяется (разрешены все агенты, если не ограничены mount-ом).

### 6.5 Секция `mounts`
Поля mount entry:
- `source` (обязателен) — адрес монтируемой папки в хостовой файловой системе.
- `target` (optional, default `/home/ubuntu/<basename(source)>`) — адрес монтирования внутри VM.
- `backup` (optional, default `<source_parent>/backups-<basename(source)>`) — адрес папки резервных копий в хостовой файловой системе.
- `interval` (optional, default `5`, >0) — интервал инкрементальных резервных копий, в минутах.
- `max_backups` (optional, default `100`, >0) — максимальное количество снапшотов; после достижения лимита включается чистка старых.
- `backup_clean_method` (optional, default `thin`, одно из `tail|thin`) — метод очистки:
  - `tail`: удалять самые старые снапшоты (хвост истории), оставляя последние `N`;
  - `thin`: логарифмическое прореживание (больше плотности в свежем диапазоне, меньше в старом, но старые точки во времени тоже сохраняются).
- `first_backup` (optional, default `true`) — делать ли блокирующий pre-run snapshot перед стартом агента, если backup-цепочка уже существует.
- `vm` (optional) — VM для этого mount; если не задан, используется первая VM из `vms`.
- `allowed_agents` (optional) — список имён агентов из секции `agents` или строка имён, разделённых запятыми.
  - если поле задано, `run` из этого `source` (или любой подпапки) разрешён только для перечисленных агентов;
  - если поле отсутствует, применяются ограничения из `vms.<vm>.allowed_agents` (если они заданы), иначе ограничение не применяется.

Нормализация:
- пути приводятся к абсолютным через `expanduser().resolve()`;
- если путь в команде указывает на подпапку внутри `source`, выбирается наиболее специфичное совпадение (`longest-prefix`).
- `first_backup` валидируется как булево значение.
- `allowed_agents` валидируется как список непустых строк (из YAML-списка или строки `a, b, c`); каждое имя `strip`-ится и должно существовать в `agents`.
- та же валидация `allowed_agents` применяется и для `vms.<vm>.allowed_agents`.

### 6.6 Секция `agents`
Поля:
- `type` (обязателен) — тип агента: `aider`, `qwen`, `forgecode`, `codex`, `opencode`, `codex-glibc`, `codex-glibc-prebuilt`, `claude`, `cline`.
  - поддерживаемые типы и runtime-бинарники задаются registry классов в `agsekit_cli/agents_modules/`.
  - runtime-бинарники сейчас такие: `aider -> aider`, `qwen -> qwen`, `forgecode -> forge`, `codex -> codex`, `opencode -> opencode`, `codex-glibc -> codex-glibc`, `codex-glibc-prebuilt -> codex-glibc-prebuilt`, `claude -> claude`, `cline -> cline`.
  - `aider` — установка через официальный aider installer; runtime-бинарник `aider`.
  - `forgecode` — установка через официальный Forge installer; при `run` CLI всегда дополнительно задаёт `FORGE_TRACKER=false`, чтобы отключить телеметрию.
  - `codex-glibc` — установка/сборка codex из исходников с установкой бинарника `codex-glibc`.
  - `codex-glibc-prebuilt` — установка заранее собранного `codex-glibc` (glibc-compatible) из GitHub Releases проекта; по умолчанию берётся свежий тег вида `codex-glibc-rust-v<major>.<minor>.<patch>`, источник можно переопределить через `AGSEKIT_CODEX_GLIBC_PREBUILT_REPO`, `AGSEKIT_CODEX_GLIBC_PREBUILT_TAG`, `AGSEKIT_CODEX_GLIBC_PREBUILT_ASSET`; если имя ассета не задано явно, оно определяется по архитектуре VM (`codex-glibc-linux-amd64.gz` для `x86_64`, `codex-glibc-linux-arm64.gz` для `aarch64`/`arm64`); бинарник устанавливается отдельно под именем `codex-glibc-prebuilt` и может сосуществовать с `codex-glibc`.
- `env` (optional) — mapping переменных окружения, передаваемых агенту при запуске.
  - значение приводится к строке (`null` -> пустая строка).
- `default-args` (optional) — список аргументов CLI по умолчанию.
  - при `run` одноимённые пользовательские опции переопределяют default-опции.
- `vm` (optional) — одна целевая VM для агента.
- `vms` (optional) — несколько целевых VM для агента (YAML-список или строка имён, разделённых запятыми).
  - значения `vm` и `vms` объединяются (deduplicate, с сохранением порядка);
  - если `vm` и `vms` одновременно пустые/не заданы, агент считается привязанным ко всем VM из секции `vms`;
  - эта привязка используется в `status`, `install-agents` и как default-выбор VM в `run` (когда не задан `--vm` и нет mount-контекста).
- `proxychains` (optional) — proxy URL `scheme://host:port` для этого агента.
  - используется в `run` и `install-agents`;
  - если поле присутствует, оно перекрывает `vms.<vm>.proxychains` даже при пустой строке (т.е. может принудительно отключить proxychains для агента).
- `http_proxy` (optional) — HTTP proxy для `run`; формат такой же, как у `vms.<vm>.http_proxy`.
  - если поле присутствует, оно перекрывает `vms.<vm>.http_proxy`, включая явное отключение пустой строкой.

Поведение валидации:
- ошибки валидации конфига возвращаются с контекстом: путь к config-файлу, путь в YAML (например `agents.cline`) и имя блока (например Agent `cline`);
- для `agents.<name>.type` при неизвестном значении добавляется подсказка с ближайшим поддерживаемым типом (например `cilne` -> `cline`);
- при вероятной опечатке имени поля `type` (например `tpye`) в блоке агента возвращается явная ошибка про опечатку поля.
- `agents.<name>.vms` валидируется как YAML-список или строка с именами через запятую; элементы должны быть непустыми строками;
- если секция `vms` задана, каждое имя из `agents.<name>.vm` / `agents.<name>.vms` должно существовать в ней.

## 7. Модель CLI и взаимодействие режимов

### 7.1 Команды, которым конфиг НЕ требуется
Это список команд, которые могут работать без чтения project-конфига:
- `prepare`
- `up`
- `backup-once`
- `backup-repeated`
- `config-example`
- `config-gen`
- `pip-upgrade`
- `version`
- `list-bundles`
- `daemon install`
- `daemon uninstall`
- `daemon start`
- `daemon stop`
- `daemon restart`
- `daemon status`

Важно:
- `prepare` может работать без YAML-конфига, но если конфиг есть и в нём задан `global.ssh_keys_folder`, команда использует этот путь для host SSH keypair;
- `daemon install` технически может быть вызван без существующего файла конфига (путь резолвится), но practically предназначен для сценария, когда конфиг уже есть, потому что daemon-managed services читают project-конфигурацию.
- публичные команды `daemon *` поддерживаются на Linux и macOS; на Windows они печатают предупреждение, что daemon пока не реализован.
- `daemon start`, `daemon stop` и `daemon restart` не читают YAML-конфиг и управляют уже зарегистрированными backend-сервисами.
- `daemon status` не читает YAML-конфиг и показывает backend-specific состояние сервиса: на Linux это `systemd` unit и журнал, на macOS — `launchd` job и хвост stdout/stderr логов.
- `systemd *` остаётся доступным как deprecated alias: команда печатает предупреждение `используйте agsekit daemon ...` и затем вызывает соответствующий `daemon` handler.

### 7.2 Команды, которые работают через конфиг
Практически все остальные команды читают и валидируют конфиг: VM lifecycle, mounts, agent install/run, backup по mount, порт-форвардинг.

### 7.3 Интерактивный режим (архитектурное решение)
Интерактивное меню не «высечено в камне»: это текущая организация команд для удобства пользователя и она может эволюционировать.

Сейчас команды в меню сгруппированы по секциям:
- init/config
- virtual machines
- mounts
- agents/shell
- daemon control (`daemon install`, `daemon uninstall`, `daemon start`, `daemon stop`, `daemon restart`, `daemon status`)
- manual backup

Поведение fallback:
- `agsekit` без аргументов в TTY -> открывает меню;
- если в TTY не хватает обязательных аргументов -> предлагает интерактивное заполнение;
- если команда требует конфиг, а файла нет -> предлагает интерактивно указать/создать путь;
- `--non-interactive` полностью отключает prompts.

## 8. Полное CLI-поведение с user-story контекстом

### 8.1 Подготовка хоста

#### `agsekit prepare`
Зачем пользователю:
- подготовить именно хостовую машину, чтобы дальше можно было стабильно создавать/готовить VM.

Что делает:
1. Если хост запущен внутри WSL, завершает команду понятной ошибкой: WSL не поддерживается, нужно использовать обычный Linux-хост или native Windows PowerShell.
2. На native Windows сначала проверяет host-утилиты `rsync` и `ssh-keygen`; если они отсутствуют, спрашивает пользователя с default `Yes` и при согласии ставит MSYS2 через `winget install --id MSYS2.MSYS2 -e --accept-package-agreements --accept-source-agreements`, обновляет пакеты через `pacman -Syu --noconfirm`, затем ставит `rsync` и `openssh` через `pacman -S --needed --noconfirm`.
3. На native Windows после подготовки MSYS2 идемпотентно добавляет `C:\msys64\usr\bin` в текущий процесс и пользовательский `PATH`, чтобы `rsync` и OpenSSH-утилиты были доступны последующим командам.
4. Проверяет наличие `multipass`: сначала через `PATH`, затем на native Windows по стандартному пути `C:\Program Files\Multipass\bin\multipass.exe`.
5. Если `multipass` уже доступен, установку Multipass, `snapd` и связанных host-пакетов не выполняет.
6. Если `multipass` отсутствует:
   - на native Windows печатает ссылку на скачивание Multipass for Windows и предлагает открыть её, но не устанавливает Multipass автоматически;
   - на Debian-based (`apt-get`) проверяет host-пакеты (`snapd`, `qemu-kvm`, `libvirt-daemon-system`, `libvirt-clients`, `bridge-utils`) и ставит только отсутствующие, после чего ставит Multipass через `snap`;
   - на Arch Linux (`pacman`) ставит Multipass через AUR helper (`yay` или `aura`) вместе с `libvirt`, `dnsmasq`, `qemu-base`;
   - на macOS (`Darwin` + `brew`) ставит Multipass через Homebrew cask; на macOS 13+ используется текущая cask `multipass`, а на macOS <13 используется зафиксированная legacy cask Multipass `1.14.1`;
   - если `prepare`/`up` запущен с Rich progress и установка host-зависимостей требует интерактивный ввод (например, подтверждение установки MSYS2 на Windows или `sudo` внутри Homebrew installer), progress временно приостанавливается, чтобы prompt и ввод работали в обычном терминальном режиме;
   - если нет ни `apt-get`, ни `pacman`, ни поддерживаемого `brew` на macOS, завершает `prepare` ошибкой о неподдерживаемом host package manager.
7. Проверяет наличие `ssh-keygen`; на поддерживаемом Linux ставит только отсутствующий OpenSSH client package (`openssh-client` на Debian-based, `openssh` на Arch Linux), если `ssh-keygen` не найден.
8. Проверяет наличие `rsync`; если он не найден, ставит `rsync` через пакетный менеджер на поддерживаемом Linux или через `brew install rsync` на macOS.
9. При запуске внешних host-утилит (`multipass`, `rsync`, `ssh`, `ssh-keygen`) сначала использует имя команды из `PATH`, а на native Windows при отсутствии в `PATH` использует стандартные пути установки Multipass и MSYS2.
10. Использует встроенные ansible plugins проекта для первичного bootstrap VM; внешний `ansible-galaxy collection install ...` не требуется.
11. Встроенный `agsekit_multipass` connection plugin stage'ит локальные файлы через не-hidden staging-каталог в `HOME` перед `multipass transfer`, чтобы Ansible-копирование модулей не ломалось на hidden-путях вроде `~/.ansible/tmp` и не зависело от особенностей snap-based Multipass вокруг `/tmp`.
12. Создаёт SSH-ключи хоста в каталоге из `global.ssh_keys_folder` (по умолчанию `~/.config/agsekit/ssh/`); после bootstrap эти ключи используются для Ansible SSH transport, `ssh` и `portforward`.
13. Поддерживает `--debug`: включает подробный вывод внешних команд подготовки.
14. На native Windows `prepare` остаётся host-side командой, но provisioning больше не блокируется: `create-vm`, `create-vms`, `install-agents` и `up` используют guest-side Ansible control node внутри целевой Ubuntu VM, поэтому upstream-ограничение Windows control node на хосте больше не мешает этим командам.

Архитектура реализации:
- `agsekit_cli/prepare_strategies.py` определяет host-platform через `choose_prepare()` и выбирает strategy-класс: `PrepareWin`, `PrepareMacBrew`, `PrepareLinuxDeb`, `PrepareLinuxArch` или базовый fallback `PrepareBase`;
- `agsekit_cli/commands/prepare.py` остаётся CLI-обвязкой и вызывает единый `prepare_host()`, а платформенные отличия установки Multipass, `rsync`, `ssh-keygen`/MSYS2 инкапсулированы в соответствующем классе.

#### `agsekit up [--config <path>] [--debug] [--prepare/--no-prepare] [--create-vms/--no-create-vms] [--install-agents/--no-install-agents]`
Зачем пользователю:
- выполнить типовой первый подъём окружения одной командой без отдельных ручных шагов и без интерактивных вопросов.

Что делает:
1. По умолчанию последовательно выполняет:
   - `prepare`;
   - `create-vms`;
   - `install-agents --all-agents`.
2. Для этапа установки агентов не использует `--all-vms`:
   - если у агента заданы `agents.<name>.vm`/`agents.<name>.vms`, установка идёт только в эти ВМ;
   - если обе привязки пустые, агент устанавливается во все ВМ из `vms`.
3. Поддерживает отключение любого этапа через:
   - `--no-prepare`;
   - `--no-create-vms`;
   - `--no-install-agents`.
4. Если все три этапа отключены, завершает команду ошибкой.
5. Если включены `create-vms` и/или `install-agents`, но конфиг не найден:
   - при отсутствии явного `--config` и `$CONFIG_PATH` завершает команду явной ошибкой без интерактивного TUI и подсказывает либо создать конфиг через `config-gen`/`config-example`, либо указать путь к существующему файлу через `--config`;
   - при явном `--config` или `$CONFIG_PATH` возвращает обычную ошибку `Config file not found: ...`.
6. В обычном режиме показывает общий `rich` progress по выбранным этапам и вложенный прогресс текущего внутреннего шага (`prepare`, `create-vms`, `install-agents`) под ним.
7. При `--debug` отключает Rich progress и оставляет только обычный подробный вывод внутренних команд и внешних процессов.
8. Если вложенный Ansible playbook падает в обычном режиме, CLI сначала останавливает Rich progress, печатает пустую строку-разделитель, а затем выводит хвост последних скрытых строк Ansible (до 10 строк), чтобы ошибка не терялась за progress-рендерингом.
9. Если сценарий использует конфиг (включены `create-vms` и/или `install-agents`) и CLI работает на платформе с поддержанным daemon backend, после основных этапов дополнительно устанавливает или обновляет daemon для фоновых сервисов, включая `portforward`.
   - на Linux: генерирует `systemd.env`, регистрирует user systemd unit и запускает/включает его;
   - на macOS: генерирует `LaunchAgent` plist в `~/Library/LaunchAgents`, настраивает вывод в `~/Library/Logs/agsekit/daemon.stdout.log` и `~/Library/Logs/agsekit/daemon.stderr.log`, затем выполняет `launchctl bootstrap/enable/kickstart`;
   - на Windows этот этап пропускается полностью.
10. При успешном завершении печатает итоговое сообщение об успешной установке.

### 8.2 Создание конфигов

#### `agsekit config-example [destination]`
Зачем:
- быстро получить рабочий шаблон YAML-конфига на базе примера.

Что делает:
- копирует `config-example.yaml` в целевой путь;
- default path: `~/.config/agsekit/config.yaml`;
- если default already exists — пропускает копирование.

#### `agsekit config-gen [--config <path>] [--overwrite]`
Зачем:
- создать конфиг через мастер, без ручного редактирования YAML на старте.

Что делает:
- интерактивно сначала собирает `global`;
  - `global.ssh_keys_folder`;
  - `global.systemd_env_folder` (для Linux backend);
  - `global.portforward_config_check_interval_sec`;
  - `global.http_proxy_port_pool.start/end`;
- затем собирает `vms`, `mounts`, `agents`;
- для каждой VM запрашивает optional `allowed_agents`, optional `proxychains` и optional `http_proxy`;
- для агента запрашивает `type`, default `vm`, `env`, optional `proxychains` и optional `http_proxy`;
  - если для agent `proxychains` введено буквально `""`, в YAML сохраняется явная пустая строка (`proxychains: ""`);
- спрашивает путь сохранения;
- без `--overwrite` не перезаписывает существующий файл.

#### `agsekit pip-upgrade`
Зачем:
- обновить установленный `agsekit` в том же Python-окружении, где запущена CLI.

Что делает:
1. Проверяет, что `agsekit` установлен через `pip` в текущем окружении.
2. Считывает текущую версию через `pip show`.
3. На native Windows перед обновлением переисполняет команду под `python.exe` из того же venv, чтобы освободить launcher `agsekit.exe` и не упереться в WinError 32 при замене console-script launcher.
4. Выполняет `pip install agsekit --upgrade`.
5. Повторно считывает версию и печатает итог:
   - если версия изменилась: `agsekit обновлён с версии X на версию Y`;
   - если версия не изменилась: `agsekit уже и так максимальной версии - X`.

### 8.2.1 Debug-режим для внешних команд

Для всех команд, которые выполняют внешние команды инфраструктуры (`multipass`, `ansible` через текущий Python-интерпретатор, `ssh`), поддерживается флаг `--debug`.

Что делает `--debug`:
- печатает запускаемую внешнюю команду;
- печатает код завершения;
- при наличии — печатает `stdout`/`stderr`.
- отключает compact/Rich progress-режимы для длинных Ansible- и VM-операций, чтобы не смешивать progress-bar'ы с подробным логом.

Список команд с поддержкой `--debug`:
- `prepare`
- `create-vm`, `create-vms`
- `down`
- `start-vm`, `restart-vm`, `stop-vm`, `destroy-vm`
- `doctor`
- `mount`, `umount`, `addmount`, `removemount`
- `install-agents`
- `run`
- `shell`, `ssh`
- `portforward`
- `status`

### 8.3 Мониторинг статуса

#### `agsekit status [--config <path>] [--debug]`
Зачем:
- получить единый «снимок состояния» инфраструктуры без ручного запуска нескольких команд.

Что делает:
1. Показывает путь конфигурации, который реально был использован (разрешение через `--config` / `CONFIG_PATH` / default path).
2. Для каждой ВМ из конфига выводит:
   - состояние в Multipass (running/stopped/absent);
   - ресурсы из конфига (CPU/RAM/Disk) и, при расхождении, фактические значения;
   - правила `port-forwarding` и статус процесса `agsekit portforward` (запущен/остановлен/неизвестно);
   - таблицу монтирований (`source`, `target`, `backup`, interval, retention/method, last backup, backups running?).
3. Для каждой ВМ выводит:
   - список агентов из конфига и их статус установки (по проверке бинарника в ВМ), где привязка агента к ВМ вычисляется по `agents.<name>.vm + agents.<name>.vms` (если оба поля пустые — агент показывается для всех ВМ);
   - список запущенных агентных процессов (`PID`, бинарник, рабочая директория `cwd` и соответствующие имена из конфига).

Особенности:
- команда не запускает интерактивный запрос пути к конфигу; читает путь строго по стандартному порядку разрешения;
- эвристика `backups running?` считается положительной, если время последнего снапшота не старше `interval * 2`.
- для RAM/Disk подсветка mismatch в `status` использует допуск (`relative tolerance`, текущее значение `10%`), чтобы не помечать как расхождение эффективные размеры Multipass, близкие к запрошенным.
- в списке запущенных агентов скрываются дочерние процессы, если их родитель тоже распознан как агент (чтобы не дублировать один запуск несколькими PID).

#### `agsekit doctor [--config <path>] [-y] [--debug]`
Зачем:
- запустить диагностический проход по известным проблемам установки и конфигурации и безопасно авто-исправить те из них, которые уже поддерживаются.

Что делает:
1. Показывает путь реально использованного конфига.
2. Загружает все `mounts` из конфига.
3. Для каждого mount:
   - если `source` на хосте отсутствует или пустой, пропускает запись;
   - если целевая ВМ не `running`, пропускает запись;
   - если mount сейчас не зарегистрирован в Multipass, пропускает запись;
   - если `source` на хосте не пустой, а `target` внутри VM пустой/отсутствует, помечает mount как проблемный.
4. Если проблемные mount'ы найдены:
   - в интерактивном режиме запрашивает подтверждение на `sudo snap restart multipass`;
   - при `-y` выполняет рестарт без вопроса;
   - в non-interactive режиме без `-y` завершает команду ошибкой о необходимости подтверждения.
5. После рестарта повторно проверяет только проблемные mount'ы:
   - при необходимости кратко ждёт, пока `multipass list` и чтение списка mount'ов снова станут доступны после перезапуска демона;
   - после этого ещё некоторое время повторяет проверку проблемных mount'ов, чтобы дождаться фактического восстановления содержимого внутри VM, а не делать один мгновенный снимок;
   - если `target` снова не пустой, mount считается repaired;
   - если mount остаётся пустым/отсутствующим, команда завершается ошибкой.

Особенности:
- текущая реализация покрывает только первый известный класс поломки: «директория зарегистрирована в Multipass как mounted, но непустой host-path внутри VM выглядит пустым»;
- команда не пытается чинить пустые проектные папки на хосте, потому что это может быть штатным состоянием;
- команда не стартует выключенные VM автоматически.

### 8.4 Жизненный цикл VM

#### `agsekit create-vm [vm_name] [--debug]`
Зачем:
- поднять одну VM из конфига и довести её до состояния «готова для работы агента».

Что делает:
- выбирает VM (auto-select, если в конфиге одна);
- сравнивает существующую VM по `cpu/ram/disk`;
  - `cpu` сверяется строго;
  - `ram/disk` сверяются с допуском (относительный tolerance), потому что Multipass часто возвращает эффективный объём чуть меньше запрошенного;
- если VM отсутствует — создаёт;
- если параметры отличаются — сообщает mismatch (ресурсы не меняет);
- затем всегда запускает подготовку VM:
  - start;
  - host-side bootstrap SSH access и `known_hosts`;
  - prepare guest-side tooling;
  - install base packages;
  - install bundles.
- на Linux и macOS базовые пакеты и bundles ставятся через host-side Ansible SSH transport;
- на native Windows тот же provisioning выполняется через guest-side Ansible control node внутри VM против `localhost`.
- без `--debug` отображает тот же `rich` progress для шагов подготовки, ansible и install bundles, что и `create-vms`/`install-agents`;
- при `--debug` Rich progress отключается и остаётся только подробный лог внешних команд и шагов подготовки.

#### `agsekit create-vms [--debug]`
- то же самое для всех VM из конфига.
- без `--debug` отображает общий прогресс и несколько параллельных progress-bar'ов через `rich` (VM, шаги подготовки, бандлы и ansible).
- при `--debug` Rich progress отключается и остаётся обычный подробный вывод шагов и внешних команд.

#### `agsekit start-vm`, `restart-vm`, `stop-vm`, `down`, `destroy-vm` (`--debug` поддерживается)
Зачем:
- оперативное управление жизненным циклом VM.

Особенности:
- поддержка single/all режимов;
- если VM одна — имя можно не указывать;
- `restart-vm` для тех же аргументов и правил выбора целей выполняет сначала `stop-vm`, затем `start-vm`;
- `stop-vm` перед выключением размонтирует все mount-ы выбранной ВМ, которые сейчас реально зарегистрированы в Multipass;
- `stop-vm` выключает гостевую ОС изнутри через `multipass exec <vm> -- sudo poweroff`, ждёт 30 секунд и при незавершённом shutdown выполняет `multipass stop --force <vm>`;
- `down` всегда работает по всем ВМ из конфига: перед выключением проверяет текущие процессы настроенных агентов тем же способом, что и `status`; если агенты запущены, печатает список `VM -> agent names -> cwd` и в интерактивном режиме просит подтверждение `y/N`, а в неинтерактивном режиме требует `--force`;
- `down` перед остановкой ВМ на Linux и macOS пытается остановить daemon-managed services, если daemon зарегистрирован; на Windows этот шаг является no-op;
- `down --force` пропускает проверочный prompt и выключает все ВМ сразу;
- `destroy-vm` требует подтверждение (если нет `-y`), затем `delete` + `purge`.

### 8.5 Mount management

#### `agsekit mount [source_dir] [--all] [--debug]`
Зачем:
- примонтировать проект в VM перед запуском агента.

Особенности:
- поддержка выбора по точному и относительному пути;
- поддержка выбора по подпути внутри source;
- при already mounted выдает информативное сообщение и не падает.

#### `agsekit umount [source_dir] [--all] [--debug]`
- размонтирование по тем же правилам выбора mount.

#### `agsekit addmount [--vm <vm_name>] [--allowed-agents <a,b,c>] [--debug]`
Зачем:
- добавить mount entry в YAML безопасно и без ручного редактирования.

Что делает:
- запрашивает/вычисляет default значения;
- поддерживает выбор VM для новой записи:
  - non-interactive: через `--vm <name>`;
  - interactive: при нескольких VM предлагает выбрать VM;
  - если в конфиге ровно одна VM, выбирает её автоматически;
- поддерживает установку `allowed_agents`:
  - non-interactive: через `--allowed-agents qwen,codex`;
  - interactive: предлагает либо «без ограничений», либо выбрать разрешённых агентов из уже настроенных в конфиге;
- показывает summary;
- в интерактивном режиме спрашивает подтверждение;
- делает timestamp backup конфига;
- сохраняет YAML с комментариями (`ruamel.yaml`);
- опционально выполняет mount сразу (`--mount`);
- в интерактивном режиме после сохранения новой записи спрашивает `Сразу примонтировать папку? [Y/n]` / `Mount the folder right away? [Y/n]`; ответ по умолчанию — `Yes`.

#### `agsekit removemount [--debug]`
Зачем:
- удалить mount entry безопасно и не оставить «битое» состояние.

Что делает:
- выбирает entry (по source, при необходимости по `--vm`, либо через prompt);
- сначала делает `umount`;
- только после успешного `umount` редактирует YAML;
- сохраняет backup конфига.

### 8.6 Backups

#### `agsekit backup-once --source-dir ... --dest-dir ...`
Зачем:
- сделать контролируемый моментальный снапшот каталога.

Алгоритм:
0. берёт кроссплатформенный файловый lock на `<dest_dir>/backup.pid` через `portalocker` (если lock уже занят — печатает сообщение и ждёт освобождения, по умолчанию проверяя раз в минуту; интервал можно переопределить env-переменной `AGSEKIT_BACKUP_LOCK_SLEEP_SECONDS`);
1. очистка старых `-partial/-inprogress`;
2. чтение `.backupignore` + `--exclude`;
3. dry-run на изменения;
4. при изменениях: rsync в `<timestamp>-partial`;
5. rename в финальный `<timestamp>`;
6. запись `.inodes`.

Поведение:
- если изменений нет — snapshot не создаётся;
- `--progress` показывает прогресс-бар; команда rsync формируется с учётом ОС хоста: на Linux используются `--progress --info=progress2`, на macOS (`Darwin`) и Windows — только `--progress`, чтобы не падать на старых bundled rsync;
- stdout/stderr rsync декодируются tolerant-режимом с replacement для невалидных байтов, чтобы имена файлов или системный вывод не в UTF-8 не прерывали backup-процесс Python-исключением;
- коды rsync `23/24` трактуются как warning, не fatal.
 - при выводе сообщения о занятом lock PID берётся из `backup.pid` и проверяется через `psutil.Process(pid).cmdline()`; если это не процесс `agsekit` или информацию получить нельзя, PID скрывается.

#### `agsekit backup-repeated`
Зачем:
- автоматически поддерживать backup-цепочку во время работы.

Что делает:
- в начале берёт кроссплатформенный lock на `<dest_dir>/backup.pid` через `portalocker` и удерживает его на весь цикл (в одну папку бэкапов работает только один процесс; интервал ожидания занятого lock по умолчанию 60 секунд и может быть переопределён через `AGSEKIT_BACKUP_LOCK_SLEEP_SECONDS`);
- при выполнении внутреннего `backup_once` повторный lock не берётся (чтобы не блокировать собственный процесс);
- запускает backup loop по интервалу;
- после каждого backup делает cleanup по политике;
- печатает ожидание следующего цикла;
- поддерживает `--skip-first`.

#### `agsekit backup-repeated-mount` / `backup-repeated-all`
- запускают repeated backup по mount-описаниям из конфига.

#### `agsekit backup-clean`
Зачем:
- ручная чистка backup-цепочки по mount.

Что делает:
- находит mount по source;
- применяет `tail` или `thin` с заданным `keep`.

Философский инвариант в текущей реализации:
- для команды `run` резервное копирование по mount включено по умолчанию;
- отключение возможно только явным флагом `--disable-backups` (осознанный opt-out).
- блокирующий pre-run snapshot по умолчанию включён через `mount.first_backup=true`; CLI-флаги `--first-backup` / `--no-first-backup` могут переопределять это поведение для одного запуска.

### 8.7 Установка и запуск агентов

#### `agsekit install-agents [--debug]`
Зачем:
- установить agent CLI в VM через поддерживаемый playbook.

Что делает:
- выбирает агента(ов) и VM(ы);
- если `--all-vms` не задан и позиционный `<vm>` не передан, целевые VM берутся из `agents.<name>.vm + agents.<name>.vms` (если оба поля пустые — во все VM из секции `vms`);
- определяет playbook по `agents.<name>.type`;
- перед installer playbook идемпотентно проверяет SSH key bootstrap через Multipass-host helpers;
- в рамках одного запуска `install-agents` кэширует результат SSH-подготовки по VM: после первого успешного bootstrap следующие installer playbook'и для той же VM повторно используют уже подготовленный доступ;
- на Linux и macOS запускает Ansible installer через общий host-side runner и стандартный Ansible SSH transport;
  - по умолчанию host-side runner включает компактный progress-вывод (`X/Y task-name` + progress bar) через custom callback plugin;
  - при ошибке runner допечатывает хвост последних скрытых строк Ansible (до 10 строк);
  - при `--debug` progress callback отключается и используется стандартный вывод ansible;
- на native Windows запускает тот же installer playbook через VM-local control node внутри VM против `localhost`;
  - в обычном режиме вывод остаётся на уровне high-level шагов команды без nested Ansible progress;
  - при `--debug` включается подробный вывод внешних `multipass exec` и guest-side `ansible-playbook -vvv`;
- без `--debug` показывает `rich` progress установки агентов;
- при `--debug` Rich progress тоже отключается, чтобы вывод установки оставался обычным потоковым логом;
- поддерживает proxychains override на один запуск (`--proxychains`).
- при запуске без аргументов в интерактивном TTY запрашивает выбор агента и цели установки;
- при запуске без аргументов в non-interactive режиме требует явный выбор агента (ошибка `agent_required`).
- при успешном standalone-запуске печатает явное итоговое сообщение:
  - для одного target: что агент готов к работе в выбранной ВМ;
  - для нескольких target: общее сообщение об успешной установке.
- для Node-based agent installers (`codex`, `qwen`, `opencode`, `cline`) при отсутствии `node` сначала резолвит через `nvm version-remote` последнюю доступную patch-версию поддерживаемой major-ветки и только потом выполняет `nvm install <resolved_version>`, чтобы не зависеть от поддержки short-major form вроде `nvm install 24`.
- если в одном запуске `install-agents` несколько Node-based агентов ставятся в одну и ту же VM, после первого успешного Node-based installer run CLI запоминает эту VM в локальном in-memory cache и передаёт в следующие playbook extra vars `skip_nvm_install=true` и `skip_node_install=true`, чтобы повторно не делать `nvm`/Node bootstrap.
- для Node-based agent installers проверка наличия `node` не ограничивается голым системным `PATH`: installer сначала пробует `command -v node`, а если бинарник не найден, явно загружает `{{ ansible_env.HOME }}/.nvm/nvm.sh`, делает `nvm use --silent default` и повторяет `node -v`; это предотвращает ложную переустановку Node, когда он уже установлен через `nvm`, но не виден не-login shell'у Ansible.

Инвариант CLI:
- установка агентов унифицирована и выполняется только через `install-agents` независимо от типа агента.

#### `agsekit run [run-options...] <agent_name> [agent_args...]`
Зачем:
- основной пользовательский сценарий: запустить агента внутри VM в нужной рабочей директории с безопасными backup-процессами.

Что делает:
1. определяет агента и VM;
   - при выборе VM действует порядок: `--vm` override -> VM выбранного mount -> первая VM из `agents.<name>.vm + agents.<name>.vms` -> первая VM из секции `vms`;
2. определяет mount-контекст:
   - опции команды (`--vm`, `--config`, `--workdir`, `--proxychains`, `--http-proxy`, `--disable-backups`, `--first-backup`, `--no-first-backup`, `--auto-mount`, `--skip-default-args`, `--debug`) должны быть указаны до `<agent_name>`;
   - всё, что стоит после `<agent_name>`, передаётся агенту как `agent_args`, даже если токены выглядят как флаги `agsekit`;
   - host working directory определяется как `--workdir`, если он задан, иначе как текущая директория (`cwd`);
   - если выбранная рабочая директория не существует, в интерактивном режиме спрашивает `Папка проекта не найдена, вы хотите запустить агента во временной папке? [y/N]` / `Project folder was not found. Run the agent in a temporary folder? [y/N]`;
   - если выбранная рабочая директория существует, но не соответствует ни одному mount, в интерактивном режиме спрашивает `Текущая папка не входит в монтируемые папки, вы хотите запустить агента во временной, не примонтированной папке? [y/N]` / `Current folder is outside the mounted folders. Run the agent in a temporary, unmounted folder? [y/N]`;
   - при подтверждении выбирает VM без mount-контекста, создаёт внутри VM директорию `/tmp/run-{random}` и запускает агента в ней без бэкапов;
   - при отказе завершает `run` без старта агента;
   - в non-interactive режиме отсутствующая рабочая директория или директория вне mounts остаётся ошибкой;
   - если выбранная рабочая директория существует, по ней ищет mount;
   - если подходящий mount не найден и интерактивный fallback не подтверждён — завершает команду с ошибкой;
   - если mount найден, но сейчас не зарегистрирован в Multipass, в интерактивном режиме спрашивает `Папка {source} сейчас не примонтирована. Примонтировать? [Y/n]` / `Folder {source} is not mounted right now. Mount it? [Y/n]`;
   - если передан `--auto-mount`, команда выполняет mount автоматически и не задаёт этот вопрос даже в интерактивном режиме;
   - при подтверждении выполняет `multipass mount` и продолжает запуск;
   - при отказе завершает `run` без старта агента;
   - в non-interactive режиме при найденном, но не примонтированном mount команда завершается ошибкой, если не передан `--auto-mount`;
3. определяет рабочую директорию в VM: либо на основе mount и относительного подпути внутри него, либо как временную `/tmp/run-{random}` при подтверждённом запуске из отсутствующей host-папки;
4. определяет эффективное ограничение агентов:
   - сначала `mount.allowed_agents` (если задано для выбранного mount);
   - иначе `vm.allowed_agents` выбранной VM (если задано);
   - иначе ограничений нет;
5. строит runtime-адаптер агента через registry `agsekit_cli/agents_modules/`;
6. собирает env агента через `agent.build_env()`;
   - базово берёт `agents.<name>.env`;
   - agent-specific правила (например `forgecode -> FORGE_TRACKER=false`) задаются в соответствующем классе агента;
7. проверяет effective `allowed_agents`;
8. если mount-контекст найден и этот mount реально зарегистрирован в Multipass:
   - сравнивает выбранную host-папку (`--workdir` или `cwd`) с соответствующей директорией внутри VM;
   - если host-папка не пустая, а VM-папка пустая/отсутствует, выводит warning с советом запустить `agsekit doctor`;
   - после warning в интерактивном режиме запрашивает подтверждение `Всё равно запустить агента? [y/N]` / `Start the agent anyway? [y/N]`;
   - ответ по умолчанию — `No`; при отказе запуск прерывается до старта агента;
9. backup-логика перед стартом агента:
   - effective `first_backup` определяется в порядке приоритета: `--first-backup` -> `--no-first-backup` -> `mount.first_backup` (default `true`);
   - если backup-цепочки ещё нет, команда всегда делает initial backup до старта агента независимо от effective `first_backup`;
   - если backup-цепочка уже существует и effective `first_backup=true`, команда делает один блокирующий `backup_once` до запуска агента;
   - если backup-цепочка уже существует и effective `first_backup=false`, этот блокирующий pre-run snapshot пропускается;
   - после любого выполненного блокирующего snapshot сразу выполняется cleanup по правилам mount;
10. если не передан `--disable-backups`, запускает фоновый `backup-repeated` и пишет лог в `backup.log`;
   - если blocking snapshot уже был сделан в этом запуске (из-за пустой backup-цепочки или effective `first_backup=true`), фоновый процесс стартует с `--skip-first`, чтобы не запускать немедленный повторный цикл;
   - если передан `--disable-backups`, фоновый `backup-repeated` не стартует, но initial/pre-run snapshot по правилам выше всё равно может быть выполнен;
11. запускает агента через один `multipass exec`, который внутри VM вызывает bundled wrapper `/usr/bin/agsekit-run_agent.sh`: wrapper проверяет наличие runtime-бинарника, при необходимости загружает `nvm`, выставляет env, подключает `proxychains`/`http_proxy` и затем делает `exec` агентного процесса;
12. по завершении агента останавливает backup-процесс.

Инвариант CLI:
- запуск агентов унифицирован и выполняется только через `run <agent_name>` независимо от типа агента.
- `run` по умолчанию всегда работает относительно текущей директории; отдельного позиционного пути у команды больше нет.

### 8.8 Операционный доступ и сервисный режим

#### `agsekit shell [--debug]`
- интерактивный вход в VM (`multipass shell`).

#### `agsekit ssh [--debug]`
- SSH в VM с ключом agsekit и прямой передачей доп. аргументов.

#### `agsekit portforward [--debug]`
- поднимает и мониторит SSH-туннели по `port-forwarding` правилам из конфига.
- раз в 10 секунд перечитывает конфиг-файл и пытается пересобрать effective-конфигурацию проброса портов;
- если во время такого reread конфиг удалён, недоступен или не проходит валидацию/парсинг, пишет warning и сохраняет работу на последнем успешно загруженном наборе туннелей;
- если reread снова начинает проходить успешно после ошибки чтения, пишет краткое recovery-сообщение и продолжает работать с новым валидным состоянием;
- сравнивает новый успешно загруженный набор `port-forwarding` с последним успешно применённым и при изменениях выполняет reconcile tunnel-процессов без перезапуска всей команды;
- сценарии reconcile, которые обязана покрывать реализация:
  - если появилась новая ВМ с `port-forwarding`, запускает новый SSH-туннель для неё;
  - если ВМ исчезла из конфига или у неё больше нет правил `port-forwarding`, останавливает её SSH-туннель и перестаёт его поддерживать;
  - если у существующей ВМ изменился набор правил проброса, останавливает её старый SSH-туннель и поднимает новый с актуальным набором `-L` / `-R` / `-D`;
  - если у ВМ раньше не было ни одного правила, а потом появились, поднимает SSH-туннель для этой ВМ;
  - если у ВМ были правила, но после изменения конфига не осталось ни одного, останавливает SSH-туннель для этой ВМ;
- если в текущем валидном конфиге правил `port-forwarding` нет вообще, команда не завершается, а остаётся в режиме ожидания изменений конфига.
- для запуска дочерних `ssh`-процессов пытается переиспользовать путь текущего запущенного `agsekit` (через `sys.argv[0]`), а если это невозможно, падает назад на `PATH` и затем на `sys.executable -m agsekit_cli.cli`; это нужно, чтобы `portforward` и daemon backend не зависели от наличия `~/.local/bin` в окружении.
- при ошибке туннеля сообщает, что `remote`-проброс на порты ниже 1024 внутри VM может быть причиной (из-за ограничения sshd).

#### `agsekit daemon install/uninstall/status`
- публичный интерфейс daemon-управления — это `daemon *`; `systemd *` остаётся доступным как deprecated alias и после предупреждения перенаправляет выполнение в соответствующую `daemon`-команду.
- Linux backend:
  - генерирует `systemd.env` в каталоге из `global.systemd_env_folder` (по умолчанию `~/.config/agsekit/systemd.env`);
  - регистрирует и включает user unit для фоновых сервисов, включая `portforward` (юнит не зависит от `WorkingDirectory`, используется абсолютный путь конфига);
  - использует bundled unit из самой установки `agsekit` (`agsekit_cli/systemd/agsekit-portforward.service`);
  - bundled unit запускает `agsekit portforward` через `/bin/bash -lc`, чтобы переменные из `EnvironmentFile` (`AGSEKIT_BIN`, `AGSEKIT_CONFIG`) корректно подставлялись и в путь к исполняемому файлу, и в аргументы;
  - `daemon install` на Linux записывает в `AGSEKIT_BIN` путь именно к текущему запущенному CLI, а не к случайному `agsekit` из `PATH`, если команда была запущена напрямую из другого места;
  - если `global.systemd_env_folder` отличается от стандартного каталога, CLI создаёт compatibility symlink из `~/.config/agsekit/systemd.env` на фактический env-файл;
  - если link на unit уже существует, но указывает на другую инсталляцию/checkout `agsekit`, перелинковывает его на текущий bundled unit и делает `restart`, чтобы подхватить новый `ExecStart` и env;
  - `status` показывает имя сервиса, путь к bundled unit, текущую user-systemd ссылку на unit, признак установки, состояния `is-enabled` / `is-active`, `LoadState` / `SubState`, `MainPID`, `Result`, временные метки последней активности и хвост последних записей `journalctl --user -u agsekit-portforward`, если служба установлена.
- macOS backend:
  - генерирует plist `~/Library/LaunchAgents/org.agsekit.portforward.plist`;
  - запускает `agsekit portforward --config ...` через `launchctl bootstrap/enable/kickstart`;
  - пишет stdout/stderr в `~/Library/Logs/agsekit/daemon.stdout.log` и `~/Library/Logs/agsekit/daemon.stderr.log`;
  - `status` показывает label, путь к plist, installed/loaded/enabled state, PID, last exit status и хвост stdout/stderr логов.
- Windows backend:
  - весь набор `daemon`-команд пока не реализован и печатает предупреждение без выполнения действий.
- `up` использует ту же внутреннюю логику `install` автоматически после VM/agent-этапов на поддерживаемых платформах.
- `down` использует ту же внутреннюю логику мягкой остановки daemon, но не делает uninstall.

Важно по отношению к философии проекта:
- daemon-контур отвечает за host-level background services; текущие backends регистрируют сервис, который поддерживает `portforward`.

## 9. Внутренние алгоритмы, критичные для поведения

### 9.1 Выбор mount по пути (longest-prefix)
- для `run`: входным путём служит `--workdir`, если он задан, иначе `cwd`;
- путь нормализуется (`resolve`);
- матчится либо точное совпадение, либо вложенность;
- при нескольких кандидатах выбирается наиболее специфичный (самый длинный `source`);
- при неоднозначности одинаковой глубины — ошибка.

### 9.2 Merge `default-args` с пользовательскими аргументами
- default-аргументы добавляются, если пользователь не передал одноимённую long-option;
- работает и для `--x=y`, и для split-формы `--x y`, и для флагов.

### 9.2.1 Маппинг `agent.type -> runtime binary`
- `run` и `status` используют runtime-бинарник, а не буквальное значение `type`;
- пока runtime-бинарник совпадает с `type`, но это может быть переопределено для новых агентов.

### 9.3 Проверка ресурсов при создании VM
Перед созданием новых VM:
- читаются существующие allocation (CPU/RAM) из `multipass list --format json`;
- суммируются планируемые ресурсы новых VM;
- общий объём RAM определяется через `os.sysconf` на POSIX-хостах, а при недоступности `sysconf` используется fallback `psutil.virtual_memory()`, что покрывает native Windows;
- запрещается создание, если останется меньше 1 CPU или меньше 1 GiB RAM.

### 9.4 Proxychains режим
- effective proxy определяется как `cli --proxychains override -> agents.<name>.proxychains -> vm.proxychains -> none`;
- раннер `run_with_proxychains.sh` и `proxychains_common.sh` устанавливаются на этапе подготовки VM (`vm_packages.yml`) в `/usr/bin`;
- `run` и binary precheck используют предустановленный раннер `/usr/bin/agsekit-run_with_proxychains.sh` без runtime-инициализации/копирования;
- создаётся временный proxychains config;
- команда запускается через `proxychains4`;
- в Ansible agent installers сетевые шаги выполняются через `proxychains_prefix` (без отдельного прокидывания proxy env-переменных); пакет `proxychains4`, `privoxy` и раннеры `/usr/bin/agsekit-run_with_proxychains.sh` / `/usr/bin/agsekit-run_with_http_proxy.sh` ставятся на этапе VM-wide подготовки, а agent-level `proxychains.yml` только собирает временный `/tmp/agsekit-proxychains.conf` и `proxychains_prefix`.

### 9.4.1 HTTP proxy режим для `run`
- effective `http_proxy` определяется как `cli --http-proxy override -> agents.<name>.http_proxy -> vm.http_proxy -> none`;
- `--http-proxy ""` отключает configured `http_proxy` на один запуск;
- непустой `--http-proxy <scheme://host:port>` работает как string shorthand `http_proxy`, то есть включает upstream-режим через временный VM-local `privoxy`;
- direct-режим (`http_proxy.url`) не поднимает `privoxy`;
  - агенту добавляются `HTTP_PROXY` и `http_proxy`;
- upstream-режим (`http_proxy` string или `http_proxy.upstream`) запускает временный VM-local `privoxy` через `/usr/bin/agsekit-run_with_http_proxy.sh`;
  - helper выбирает `listen` из `global.http_proxy_port_pool`, если он не задан явно;
  - helper создаёт временный конфиг `privoxy`, ждёт readiness, запускает агент и затем очищает temp-файлы и процесс;
- если effective `http_proxy` задан, runtime `proxychains` одновременно использовать нельзя;
  - в такой ситуации `run` завершается ошибкой;
  - чтобы агент использовал `http_proxy` при VM-level `proxychains`, агент должен явно отключить `proxychains: ""` или запуск должен передать `--proxychains ""`.

### 9.5 Ограничение запуска по allowed_agents (mount + VM)
- effective policy вычисляется как `mount.allowed_agents -> vm.allowed_agents -> unrestricted`;
- mount-level policy приоритетнее vm-level policy;
- проверка применяется для запуска по `source`, по подпапкам `source`, а также при автодетекте mount по `cwd`;
- если mount не выбран (запуск из директории вне mounts), применяется только `vm.allowed_agents` (если задано);
- при нарушении ограничения команда `run` завершается с ошибкой до старта агента и до запуска фоновых бэкапов.

## 10. Ansible-слой: что именно ставится

### 10.0 Универсальный запуск playbook'ов
- все вызовы Ansible playbook идут через единый helper `run_ansible_playbook(...)` в `ansible_utils.py`;
- запуск выполняется через `sys.executable -m ansible.cli.playbook`, чтобы всегда использовать тот же Python-интерпретатор, что и `agsekit` (и не зависеть от локальных `PATH`/`pyenv` переключений);
- перед запуском helper явно проверяет платформу control node и на native Windows завершает команду понятной ошибкой вместо попытки стартовать `ansible-playbook`;
- bootstrap-playbook `vm_ssh.yml` использует connection plugin `agsekit_multipass`, чтобы положить host public key в VM и синхронизировать known_hosts;
- все playbook'и после bootstrap получают extra vars `ansible_connection=ssh`, `ansible_host=<vm_ip>`, `ansible_user=ubuntu`, `ansible_ssh_private_key_file=<global.ssh_keys_folder>/id_rsa` и работают через встроенный SSH transport Ansible;
- helper предварительно считает общее количество задач по YAML (включая `include_tasks`/`import_tasks` и блоки `block`/`rescue`/`always`);
- по умолчанию включает stdout callback `agsekit_progress`:
  - печатает заголовок запуска;
  - печатает текущую задачу в формате `N/Total TaskName`;
  - печатает progress bar;
  - при ошибке печатает короткую строку `FAILED ...`;
- при запуске playbook'ов через Rich-прогресс (`progress_handler`) helper буферизует последние скрытые строки обычного вывода, строку `FAILED ...` и детали ошибки, чтобы при падении показать хвост лога (до 10 строк) уже после остановки progress-рендеринга;
- в `--debug` callback отключается, и ansible выводится в стандартном режиме.

### 10.1 Базовая подготовка VM (`vm_packages.yml`)
- `7zip`
- `git`
- `gzip`
- `privoxy`
- `proxychains4`
- `ripgrep`
- `zip`
- `zstd`
- `/usr/bin/proxychains_common.sh`
- `/usr/bin/agsekit-run_with_proxychains.sh`
- `/usr/bin/agsekit-run_with_http_proxy.sh`
- `run_with_http_proxy.sh` и `run_with_proxychains.sh` должны входить в package data Python-пакета, чтобы playbook'и подготовки VM работали не только из checkout, но и из установленного `site-packages`.

### 10.2 Install bundles (`vms.<vm>.install`)
Поддерживаемые bundles:
- `pyenv`
- `nvm`
- `python[:version]` (зависит от `pyenv`)
- `nodejs[:version]` (зависит от `nvm`)
- `rust`
- `golang`
- `docker`

Dependency resolution выполняется кодом до запуска playbooks.

Особенности идемпотентности:
- `pyenv` и `python` bundles определяют наличие pyenv по маркеру `~/.pyenv/bin/pyenv` (а не по `command -v pyenv`), чтобы повторные прогоны не зависели от shell PATH.

### 10.3 Agent installers
- `aider.yml`: установка через официальный aider install script с последующей проверкой бинарника `aider`; сетевые шаги выполняются через `proxychains_prefix`.
- `codex.yml`: установка `bubblewrap`, Node через nvm (с резолвом последнего доступного `v24.x.y` через `nvm version-remote`) + `@openai/codex`.
  - дополнительно ставится `logrotate` и конфиг `/etc/logrotate.d/codex-tui`, который ограничивает `~/.codex/log/codex-tui.log` политикой `size 100M`, `rotate 10`, `compress`, `delaycompress`, `missingok`, `notifempty`, `copytruncate`.
- `qwen.yml`: установка Node через nvm (с резолвом последнего доступного `v24.x.y` через `nvm version-remote`) + `@qwen-code/qwen-code`.
- `forgecode.yml`: установка через официальный Forge install script с последующей проверкой бинарника `forge`; сетевые шаги выполняются через `proxychains_prefix`.
- `opencode.yml`: установка Node через nvm (с резолвом последнего доступного `v24.x.y` через `nvm version-remote`) + `opencode-ai`.
- `cline.yml`: установка Node через nvm (с резолвом последнего доступного `v24.x.y` через `nvm version-remote`) + `cline`.
- Node-based installer playbooks проверяют наличие `node` сначала в текущем `PATH`, а затем через `nvm use --silent default`, чтобы установленный через `nvm` Node считался уже готовым даже в non-login shell'е Ansible.
- `claude.yml`: установка через официальный install script; сетевые шаги выполняются через `proxychains_prefix`; если нативный post-install падает, применяется fallback-установка `claude` прямой загрузкой последнего release-бинарника по официальным `latest` + `manifest.json` с проверкой `sha256`, причём release-base динамически определяется через redirect c `https://claude.ai/install.sh`, без захардкоженного bucket URL.
- `codex-glibc.yml`: установка `bubblewrap`, сборка из исходников `openai/codex`, управление swap при нехватке памяти, установка бинарника `codex-glibc`, post-build проверка.
  - дополнительно ставится тот же `logrotate`-конфиг для `~/.codex/log/codex-tui.log`.
- `codex-glibc-prebuilt.yml`: установка `bubblewrap`, разрешение подходящего GitHub Release проекта с выбором ассета по архитектуре целевой VM (`amd64`/`arm64`) и установка опубликованного `codex-glibc` бинарника под именем `codex-glibc-prebuilt` без сборки в VM; release metadata резолвится controller-side через `ansible_playbook_python -m agsekit_cli.prebuilt ...` внутри `lookup('pipe', ...)`, чтобы этот шаг не наследовал remote SSH vars из playbook extra vars.
  - дополнительно ставится тот же `logrotate`-конфиг для `~/.codex/log/codex-tui.log`.

## 11. Локализация

- Поддерживаемые языки: `en`, `ru`.
- Приоритет языка:
  1. `AGSEKIT_LANG`
  2. системная locale
  3. fallback: `en`
- Если ключ перевода отсутствует — возвращается сам ключ.

## 12. Побочные эффекты на диске

На хосте:
- installer `scripts/install/install.sh` создаёт per-user venv в `~/.local/share/agsekit/venv`, symlink `~/.local/bin/agsekit`, а при необходимости добавляет `export PATH="$HOME/.local/bin:$PATH"` в shell startup files;
- Windows installer `scripts/install/install.ps1` создаёт per-user venv в `%USERPROFILE%\.local\share\agsekit\venv`, wrapper `%USERPROFILE%\.local\bin\agsekit.cmd`, а при необходимости добавляет `%USERPROFILE%\.local\bin` в пользовательский `PATH`; после изменения пользовательского `PATH` установщик обновляет `PATH` текущей PowerShell-сессии из Machine+User PATH, чтобы не терять стандартные entries вроде WindowsApps/`winget`;
- `~/.config/agsekit/config.yaml`
- SSH keypair в каталоге из `global.ssh_keys_folder` (по умолчанию `~/.config/agsekit/ssh/id_rsa` и `id_rsa.pub`)
- `systemd.env` в каталоге из `global.systemd_env_folder` (по умолчанию `~/.config/agsekit/systemd.env`) на Linux
- compatibility symlink `~/.config/agsekit/systemd.env`, если `global.systemd_env_folder` переопределён
- `~/Library/LaunchAgents/org.agsekit.portforward.plist` на macOS
- `~/Library/Logs/agsekit/daemon.stdout.log` и `~/Library/Logs/agsekit/daemon.stderr.log` на macOS
- backup snapshots `.../<timestamp>`
- временные backup dirs `*-partial` / `*-inprogress`
- `backup.log` для фоновых backup-процессов
- timestamp backups конфига при `addmount`/`removemount`

Внутри VM:
- системные proxychains helper scripts в `/usr/bin`
- системный HTTP proxy helper script в `/usr/bin`
- установленный agent/toolchain stack по выбранным playbooks

## 13. Ограничения и текущие особенности

- Нельзя in-place менять `cpu/ram/disk` у уже созданной VM (только детект mismatch).
- `shell` не включает автоматически порт-форвардинг; для постоянных туннелей используется `portforward`/`daemon`.
- Источником истины для текущего поведения являются код и тесты.

## 14. Влияние на развитие проекта

При доработке инструмента этот документ полезно читать как карту компромиссов:
- если меняется UX команд, нужно учитывать двойной режим (interactive + automation);
- если меняется структура конфига, нужно сохранить понятные defaults и миграционную предсказуемость;
- если меняется backup-логика, важно сохранить базовую user-гарантию: «запуск агента не оставляет пользователя без отката»;
- если добавляются новые типы агентов, нужно расширять и схему `agents.type`, и Ansible installers, и тестовое покрытие.
- если развивается observability/статус-интерфейс, нужно двигаться в сторону философской цели «прозрачность состояния» (VM, mounts, forward rules, backup health, активные процессы).
- если расширяется сервисный режим, нужно синхронизировать реализацию с философской целью более широкого daemon orchestration.

Иными словами, `agsekit` — это не только набор команд, а операционная модель безопасной работы с агентами. Именно эта модель должна оставаться консистентной при любых будущих изменениях.
