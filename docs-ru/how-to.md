# Практические How-To

На этой странице собраны короткие практические рецепты, которые полезны на раннем этапе использования.

## Монтирование папок

* Не используйте папки, в именах которых содержатся не-ascii-символы, это ограничение multipass

## Self-hosted OpenAI-compatible API

Если у вас есть своя собственная self-hosted LLM с OpenAI API, то её настройка в различных агентах иногда не слишком тривиальна.

Здесь приведены инструкции для некоторых из поддерживаемых агентов (список обновляется)

Предположим что у вас есть данные (для примера)

```
OPENAI_BASE_URL=http://127.0.0.1:8080/v1 - адрес вашего vLLM сервера инференса
OPENAI_API_KEY="my-very-secure-key"
OPENAI_MODEL="Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
```
  
### Qwen

Параметры можно передать через env-переменные. 

1. Меняем конфигурацию agsekit, задавая env-переменные:

```yaml
...
agents:
...
  qwen:
    type: qwen
    env:
      OPENAI_API_KEY: "my-very-secure-key"
      OPENAI_BASE_URL: "http://127.0.0.1:8080/v1"
      OPENAI_MODEL: "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
...
```

2. После этого запускаем qwen, и он спросит, какое использовать API: Облачное или локальное. Нужно выбрать локальное, а данные подключения сами подставятся из env

```shell
agsekit run qwen
```

### Cline

Параметры можно передать специальной командой.

1. Допустим, у вас в конфигурации agsekit есть агент cline

```yaml
...
agents:
...
  cline:
    type: cline
```

2. Выполняем команду:

```shell
agsekit run cline auth -p openai -k "my-very-secure-key" -m "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8" -b "http://127.0.0.1:8080/v1"
```

После этого запускаем 

```shell
agsekit run cline 
```

и настройка уже будет выполнена

### ForgeCode

1. Зададим env-переменные в конфиге agsekit

```yaml
...
agents:
...
  forgecode:
    type: forgecode 
    env:
      OPENAI_API_KEY: "my-very-secure-key"
      OPENAI_URL: "http://127.0.0.1:8080/v1"
```

2. Запускаем агента

```shell
agsekit run forgecode
```

3. При первом запуске откроется окно выбора провайдера

Выбираем OpenAI Compatible

Все остальные данные подтянутся из env-переменных, а вариант сетки (если у вас их несколько) можно выбрать отдельной командой

### Aider

1. Настраиваем env-переменные и аргументы в конфиге agsekit:

```yaml
...
agents:
...
  aider:
    type: aider
    proxychains: ""
    env:
      OPENAI_API_KEY: "my-very-secure-key"
      OPENAI_API_BASE: "http://127.0.0.1:8080/v1"
    default-args:
      - "--model"
      - "openai/Qwen/Qwen3-Coder-30B-A3B-Instruct"
      - "--no-gitignore"

```

Обратите внимание, что перед названием вашей сетки в `--model` надо добавить префикс "openai/" - он отвечает за определение "типа провайдера"

2. Запускаем агента

```shell
agsekit run aider
```

### Другие агенты

... В разработке ...




- [Поддерживаемые агенты](agents.md)
- [run](commands/run.md)

## Запуск codex и claude-code при ограничениях доступа

Допустим у вас отсутствует доступ к API OpenAI и Anthropic, что мешает вам пользоваться codex/claude-code.

При этом, предположим у вас есть доступ по SSH на некий сервер в интернете/у вас дома, с которого доступ к упомянутым API не ограничен.

Что можно сделать?

1) Настройка постоянного socks-proxy

Если вы пользуетесь linux/macos, вы можете использовать auotssh чтобы настроить постоянный проброс порта socks5-proxy.

Написать скрипт вроде такого:
```shell
#!/bin/bash

# здесь ваш хост для подключения по ssh
SSH_USER_HOST="user@remove-vps-host.com"
# Путь к приватному ключу для ssh
PRIV_KEY="/home/user/.ssh/id_rsa"
# Порт на котором будет слушать socks-proxy
LISTEN="127.0.01:8087"

killall autossh

nohup autossh -M 10984 -N -o "PubkeyAuthentication=yes" -o "PasswordAuthentication=no" -i /"$PRIV_KEY" -o "BatchMode=yes" -o "ConnectTimeout=10" \
    $SSH_USER_HOST -D $LISTEN &
```

Положить его в файл ~/autossh.sh, сделать исполняемым, и добавить в автозагрузку системы любым удобным для вас способом.

2) Настройка проброса порта и proxychains

В конфигурации agsekit:

```shell
vms:
  agents-ubuntu:
    ...
    port-forwarding:
      - type: remote
        # На этот порт хоста будет пробрасываться соединение 
        host-addr: 127.0.0.1:8087
        # при подключении на этот порт ВМ
        vm-addr: 127.0.0.1:8087

agents:
  codex:
    type: codex-glibc-prebuilt # используем этот тип, так как он поддерживает proxychains
    # Настраиваем proxychains на порт который ведёт на socks5-прокси хоста
    proxychains: socks5://127.0.0.1:8087
    
  claude:
    type: claude
    # Настраиваем http-proxy на запуск временного proxify со случайным портом, и прокидыванием траффика на socks5-прокси хоста
    http_proxy: socks5://127.0.0.1:8087
```

В linux можно настроить демон systemd командой `agsekit systemd install` - и проброс портов будет поддерживаться автоматически

В windows / macos можно запустить в отдельном терминале `agsekit portforward` и проброс портов будет поддерживаться пока жив этот терминал

## См. также

- [Сеть и прокси](networking.md)
- [Сетевые команды](commands/networking.md)
- [systemd](commands/systemd.md)
