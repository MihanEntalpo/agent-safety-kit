# Конфигурация

`agsekit` использует YAML-файл, обычно `~/.config/agsekit/config.yaml`.

Порядок поиска:

1. `--config <path>`
2. `CONFIG_PATH`
3. `~/.config/agsekit/config.yaml`

## Верхнеуровневые секции

- `global`
- `vms`
- `mounts`
- `agents`

## `global`

Основные поля:

- `ssh_keys_folder`: каталог хостовых SSH-ключей для доступа к VM.
- `systemd_env_folder`: Linux-only путь для `systemd.env`.
- `portforward_config_check_interval_sec`: интервал перечитывания конфига для `portforward`.
- `http_proxy_port_pool.start` / `http_proxy_port_pool.end`: диапазон локальных портов для временных proxy helper'ов.

## `vms`

Каждая VM может описывать:

- `cpu`
- `ram`
- `disk`
- `cloud-init`
- `proxychains`
- `http_proxy`
- `allowed_agents`
- `port-forwarding`

## `mounts`

Каждый mount описывает:

- `source`
- `vm`
- `target`
- `backup`
- `interval`
- `max_backups`
- `backup_clean_method`
- `allowed_agents`

Mount связывает хостовую папку проекта с путём внутри VM и описывает backup policy.

## `agents`

Каждый agent profile может описывать:

- `type`
- `vm`
- `vms`
- `default-args`
- `env`
- `proxychains`
- `http_proxy`

## Пример

```yaml
global:
  ssh_keys_folder: ~/.config/agsekit/ssh

vms:
  agent-ubuntu:
    cpu: 4
    ram: 4G
    disk: 20G

mounts:
  - source: /home/user/project
    vm: agent-ubuntu
    target: /home/ubuntu/project
    backup: /home/user/backups-project
    interval: 5

agents:
  qwen:
    type: qwen
    vm: agent-ubuntu
```

## Связанные темы

- подробности `proxychains` и `http_proxy` в [networking.md](networking.md)
- backup policy в [backups.md](backups.md)
- поведение команд в [commands/README.md](commands/README.md)

## См. также

- [Быстрый старт](getting-started.md)
- [Сеть](networking.md)
- [Бэкапы](backups.md)
