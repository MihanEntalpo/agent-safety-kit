# Конфигурация

`agsekit` использует YAML-файл, обычно `~/.config/agsekit/config.yaml`.

Также, в любой команде `agsekit` можно переопределить путь к config-файлу при запуске:

1. аргументом командной строки`--config <path>`
2. переменной окружения `CONFIG_PATH`

## Полный пример конфиг-файла с комментариями:

```yaml
# Глобальная конфигурация для всего agsekit в целом
global: 
  # Переопределение папки для ssh-ключей, по умолчанию ~/.config/agsekit/ssh. Сюда agsekit кладёт ssh-ключи.
  ssh_keys_folder: null
  # Переопределение папки env-переменных для systemd-службы (используется в linux)
  systemd_env_folder: null
  # Частота проверки конфигурации демоном проброса портов, по умолчанию каждые 10 секунд
  portforward_config_check_interval_sec: 10 
  # Диапазон портов для динамического выделения при запуске proxy-сервера, по умолчанию от 48000 до 49000
  http_proxy_port_pool:
    start: 48000
    end: 49000

# Описание виртуальных машин. Нужна как минимум одна, задать можно сколько угодно 
vms:
  # Название ВМ, после создания лучше не менять
  agents-personal:
    # Количество ядер CPU
    cpu: 2
    # количество RAM
    ram: 4G
    # Объем диска
    disk: 20G
    # Здесь можно задать полноценную конфигурацию cloud-init для multipass
    cloud-init: {}
    # Включить proxychains для всех агентов, запускаемых в этой ВМ, и настроить его на указанный адрес
    proxychains: socks5://127.0.0.1:18881
    # Включить портфорвардинг - проброс портов внутрь и наружу ВМ, на базе ssh-туннелей  
    port-forwarding:
      # Типы бывают: remote, local, socks
      # remote - значит подключение изнутри ВМ на хост
      - type: remote
        host-addr: 127.0.0.1:28881
        vm-addr: 127.0.0.1:18881
      # local - значит подключение из хоста в ВМ
      - type: local
        host-addr: 127.0.0.1:8080
        vm-addr: 127.0.0.1:80
      # socks5 - открыть в ВМ порт socks5-прокси ведущий на хост
      - type: socks5
        vm-addr: 127.0.0.1:11800
    # Установить готовые "Пакеты ПО" при создании ВМ
    install:
      - docker
      - pyenv
      - python
  # Ещё одна ВМ, в данном примере их 2, одна для личных проектов, вторая для рабочих
  agents-nda:
    # Также, количество cpu, ram, диска
    cpu: 2
    ram: 4G
    disk: 20G
    cloud-init: {}
    install:
      - docker
      - pyenv
      - python
    # Список агентов, которые можно запускать в ВМ, остальные - нельзя. Если не указано - тогда можно всё.
    allowed_agents: qwen, cline

# Монтирование папок в ВМ
mounts:
  # source - это путь к папке в основной системе
  - source: /home/user/work/work-project-1
    # Папка для бэкапов в основной ОС, если не указана, будет задана в {путь к папка}/backups-{имя папки}
    backup: /home/user/work/backups-work-project-1
    # Куда монтируется папка внутри ВМ
    target: /home/ubuntu/work-project-1
    # Список агентов, которые можно запускать с этой папкой, остальные - нельзя. Если не указано - можно все.
    allowed_agents: [qwen, cline]
    # ВМ, куда монтировать эту папку. Если не указано - будет примонтирована в ПЕРВУЮ ВМ из списка
    vm: agents-nda    
    # Интервал создания бэкапов, в минутах, по умолчанию 5
    interval: 5
    # Скольпо максимум хранить бэкапов, по умоланию 100
    max_backups: 100
    # Каким методом очищать старые бэкапы: thin или tail. 
    # "thin" - лорагифмическое прореживание (давних бэкапов меньше, свежих больше), хранение на большую глубину
    # 'tail' - просто удалять с конца
    backup_clean_method: thin  

# Конфигурация агентов
agents:
  # Имя агента может быть любым, например "superagent", именно по нему идёт обращение при запуске `agsekit run <agent>`
  qwen:
    # Тип агента - один из поддерживаемых: qwen, codex, claude, cline, aider, forgecode, opencode, codex-glibc, codex-glibc-prebuilt
    type: qwen
    # Переменные окружения для агента
    env:
      # Здесь, например, задаётся self-hosted модель.      
      OPENAI_API_KEY: "Your-Api-Key"
      OPENAI_BASE_URL: "http://127.0.0.1:8080"
      OPENAI_MODEL: "Qwen/Qwen3-Coder-9B"
    # В какой ВМ запускается по-умолчанию, если нет рабочей папки, либо она есть в обоих ВМ 
    vm: agents-nda
  # Вот пример агента того же типа, что и раньше, но с другим именем 
  qwen-cloud:
    type: qwen
    vm: agents-personal
  codex:
    # codex-glibc-prebuilt - это собранный вручную агент codex, поддерживающий работу через proxychains
    type: codex-glibc-prebuilt
    # Агенту можно передать аргуметы командной строки по умолчанию
    default-args:
      - "--sandbox=danger-full-access"  
  claude:
    type: claude
    # В агенте можно переопределить proxychains (пустая строка её отключает)
    proxychains: ""
    # Также, в агенте можно задать http-proxy
    http_proxy: socks5://127.0.0.1:18881

```

## Подробное описание каждого параметра:

* `global.ssh_keys_folder`
  * Указывает путь к папке с ssh-ключами. Команды `agsekit up`, `agsekit prepare` выполняют идемпотентное создание ssh ключей и добавление их в ВМ, для дальнейшего функционирования команд `agsekit ssh` и `agsekit portforward`.
  * См. [prepare](commands/prepare.md) и [сетевые команды](commands/networking.md)
  * По умолчанию ~/.config/agsekit/ssh
* `global.systemd_env_folder`
  * Указывает путь к папке с .env-файлом для запуска systemd-службы (используется только в linux/WSL)
  * См. [systemd](commands/systemd.md)
  * По умолчанию ~/.config/agsekit
* `global.portforward_config_check_interval_sec`
  * Как часто нужно перечитывать конфигурацию, чтобы, при изменении списка портов, менять ssh-туннели
  * Команда `agsekit portforward` а также демон запускаемый через `agsekit systemd start` выполняют проброс портов, и при изменении конфигурации - динамически обновляют порты
  * См. [Port Forwarding](networking.md#port-forwarding) и [portforward](commands/networking.md)
* `global.http_proxy_port_pool` 
  * Диапазон портов, из которых выбирается порт при запуске прокси-сервера
  * Команда `agsekit run <agent>` может запускать прокси-сервер, если это задано в конфигурации или аргументе командной строки, и если у него не задан listen-порт - берётся случайный из диапазона
  * См. [HTTP_PROXY](networking.md#httpproxy)
  * По умолчанию `{"start": 48000, "end": 49000}`
* `vms` 
  * Набор виртуальных машин, виртуальных машин может бысть сколько угодно, но не менее одной
* `vms.<vm_name>`
  * Конфигурация конкретной виртуальной машины. Её имя - это уникальный идентификатор, который не стоит менять если ВМ уже создана, иначе начнётся серьёзная путанница
  * mutlipass не умеет переименовывать ВМ, поэтому самое простое, если хотите переименовать - это уничтожить старую и создать новую.
* `vms.<vm_name>.cpu`
  * Количество ядер процессора
  * Утилизируется по мере использования виртуальной машиной
  * Рекомендуется хотя-бы 2 ядра, но при нехватке как-то будет работать и с одним
* `vms.<vm_name>.ram`
  * Объём оперативной памяти для ВМ
  * Допускаются значения в формате Multipass, например `4G` или `4096M`
* `vms.<vm_name>.disk`
  * Размер диска ВМ
  * Допускаются значения в формате Multipass, например `20G`
* `vms.<vm_name>.cloud-init`
  * Полноценная конфигурация `cloud-init`, которая передаётся в `multipass launch` [create-vm / create-vms](commands/create-vm.md)
  * Можно не указывать, если дополнительная начальная настройка ВМ не нужна
* `vms.<vm_name>.proxychains`
  * URL прокси для запуска агентов через `proxychains` в этой ВМ, см. [Proxychains](networking.md#proxychains)
  * Поддерживаются схемы `http`, `https`, `socks4`, `socks5`
  * Агент может переопределить это значение через `agents.<agent_name>.proxychains`; пустая строка отключает `proxychains`
* `vms.<vm_name>.http_proxy`
  * HTTP proxy для `agsekit run` на уровне ВМ, см. [HTTP_PROXY](networking.md#httpproxy)
  * Может быть строкой `scheme://host:port`, тогда agsekit поднимет временный `privoxy` внутри ВМ
  * Может быть объектом `{url: http://host:port}`, тогда агенту просто будут переданы `HTTP_PROXY` и `http_proxy`
  * Может быть объектом `{upstream: scheme://host:port, listen: 127.0.0.1:48080}`, тогда `privoxy` будет слушать явно заданный адрес
  * Агент может переопределить это значение через `agents.<agent_name>.http_proxy`
* `vms.<vm_name>.http_proxy.url`
  * Готовый HTTP/HTTPS proxy URL для direct-режима
  * В этом режиме `privoxy` не запускается
* `vms.<vm_name>.http_proxy.upstream`
  * Вышестоящий прокси для upstream-режима через временный `privoxy`
  * Поддерживаются схемы `http`, `https`, `socks4`, `socks5`
* `vms.<vm_name>.http_proxy.listen`
  * Адрес или порт, на котором временный `privoxy` будет слушать внутри ВМ
  * Если указать только порт, например `48080`, он превратится в `127.0.0.1:48080`
  * Если не указан, порт выбирается из `global.http_proxy_port_pool`
* `vms.<vm_name>.port-forwarding`
  * Список правил проброса портов для команды `agsekit portforward`
  * Каждое правило поднимается через SSH-туннель
  * См. [Port Forwarding](networking.md#port-forwarding) и [сетевые команды](commands/networking.md)
* `vms.<vm_name>.port-forwarding[].type`
  * Тип правила: `local`, `remote` или `socks5`
  * `local` открывает порт на хосте и ведёт его в ВМ
  * `remote` открывает порт в ВМ и ведёт его на хост
  * `socks5` открывает SOCKS5-порт внутри ВМ
* `vms.<vm_name>.port-forwarding[].host-addr`
  * Адрес на стороне хоста в формате `host:port`
  * Обязателен для правил `local` и `remote`
  * Для `socks5` не используется
* `vms.<vm_name>.port-forwarding[].vm-addr`
  * Адрес на стороне ВМ в формате `host:port`
  * Обязателен для всех правил `port-forwarding`
* `vms.<vm_name>.install`
  * Список готовых install-bundles, которые будут установлены при `create-vm`, `create-vms` или `up` [create-vm / create-vms](commands/create-vm.md) и [up](commands/up.md)
  * Доступные bundles:
    * `pyenv` - устанавливает pyenv и зависимости для сборки Python
    * `nvm` - устанавливает nvm и shell-init hooks
    * `python` - устанавливает pyenv и Python; поддерживает версию, например `python:3.12.2`
    * `nodejs` - устанавливает nvm и Node.js; поддерживает версию, например `nodejs:20`
    * `rust` - устанавливает rustup и Rust toolchain
    * `golang` - устанавливает Go toolchain через apt
    * `docker` - устанавливает Docker Engine и Docker Compose через apt-репозиторий Docker
* `vms.<vm_name>.allowed_agents`
  * Список агентов, которых разрешено запускать в этой ВМ
  * См. [run](commands/run.md)
  * Можно задавать YAML-списком или строкой через запятую
  * Если не указано, ограничение на уровне ВМ не применяется
  * Ограничение mount имеет больший приоритет, чем ограничение ВМ
* `mounts`
  * Список папок хоста, которые agsekit может монтировать в ВМ
  * Каждая запись также задаёт backup-политику для этой папки
  * См. [команды монтирования](commands/mount.md)
* `mounts[].source`
  * Путь к папке на хосте
  * Обязательный параметр
  * При запуске из подпапки agsekit выбирает самое точное совпадение по `source`
* `mounts[].backup`
  * Папка на хосте, куда складываются снапшоты
  * См. [Бэкапы](backups.md)
  * Если не указана, используется `<source_parent>/backups-<source_name>`
* `mounts[].target`
  * Путь внутри ВМ, куда монтируется `source`
  * Если не указан, используется `/home/ubuntu/<source_name>`
* `mounts[].allowed_agents`
  * Список агентов, которым разрешено работать с этой папкой
  * См. [run](commands/run.md)
  * Можно задавать YAML-списком или строкой через запятую
  * Если указано, перекрывает `vms.<vm_name>.allowed_agents`
* `mounts[].vm`
  * Имя ВМ, куда монтируется папка
  * Если не указано, используется первая ВМ из секции `vms`
* `mounts[].interval`
  * Интервал повторяющихся бэкапов в минутах
  * См. [Бэкапы](backups.md)
  * По умолчанию `5`
* `mounts[].max_backups`
  * Максимальное количество снапшотов для этой папки
  * См. [Бэкапы](backups.md)
  * По умолчанию `100`
* `mounts[].backup_clean_method`
  * Метод очистки старых бэкапов: `thin` или `tail`
  * См. [Бэкапы](backups.md)
  * `thin` логарифмически прореживает историю и сохраняет большую глубину
  * `tail` просто удаляет самые старые снапшоты
  * По умолчанию `thin`
* `agents`
  * Набор профилей агентов
  * Имя профиля используется в команде `agsekit run <agent_name>`
  * См. [Поддерживаемые агенты](agents.md)
* `agents.<agent_name>`
  * Конфигурация конкретного агента
  * Один и тот же тип агента можно описать несколькими профилями с разными настройками
* `agents.<agent_name>.type`
  * Тип агента
  * См. [Поддерживаемые агенты](agents.md)
  * Поддерживаемые значения: `aider`, `qwen`, `forgecode`, `codex`, `opencode`, `codex-glibc`, `codex-glibc-prebuilt`, `claude`, `cline`
  * Обязательный параметр
* `agents.<agent_name>.env`
  * Переменные окружения, которые будут переданы процессу агента
  * Значения приводятся к строкам; `null` превращается в пустую строку
* `agents.<agent_name>.default-args`
  * Аргументы командной строки, которые agsekit добавляет при запуске агента
  * См. [run](commands/run.md)
  * Если пользователь передал опцию с тем же именем вручную, значение из `default-args` пропускается
  * Можно отключить все default-args флагом `agsekit run --skip-default-args <agent>`
* `agents.<agent_name>.vm`
  * Одна ВМ по умолчанию для этого агента
  * См. [run](commands/run.md)
  * Используется, когда агент запущен не в папке монтирования и ВМ не выбрана через аргумент `--vm`
  * По умолчанию - первая ВМ в списке (если в ней разрешён этот агент)
* `agents.<agent_name>.vms`
  * Список ВМ, к которым привязан агент, используется не для ограничений запуска, а для команд install-agents / status
  * См. [install-agents](commands/install-agents.md) и [status](commands/status.md)
  * Можно задавать YAML-списком или строкой через запятую
  * По умолчанию считается что здесь все ВМ
* `agents.<agent_name>.proxychains`
  * Proxychains-настройка для конкретного агента
  * См. [Proxychains](networking.md#proxychains)
  * Перекрывает `vms.<vm_name>.proxychains`
  * Пустая строка отключает `proxychains` для агента
* `agents.<agent_name>.http_proxy`
  * HTTP proxy для конкретного агента
  * См. [HTTP_PROXY](networking.md#httpproxy)
  * Формат такой же, как у `vms.<vm_name>.http_proxy`
  * Перекрывает `vms.<vm_name>.http_proxy`; пустая строка отключает `http_proxy` для агента
* `agents.<agent_name>.http_proxy.url`
  * Готовый HTTP/HTTPS proxy URL для direct-режима
  * Агенту передаются переменные `HTTP_PROXY` и `http_proxy`
* `agents.<agent_name>.http_proxy.upstream`
  * Вышестоящий прокси для upstream-режима через временный `privoxy`
  * Поддерживаются схемы `http`, `https`, `socks4`, `socks5`
* `agents.<agent_name>.http_proxy.listen`
  * Адрес или порт временного `privoxy` внутри ВМ
  * Если не указан, порт выбирается из `global.http_proxy_port_pool`
