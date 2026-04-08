# Troubleshooting

Эта страница собирает самые типичные операционные проблемы.

## `multipass` зависает или падает

Проверьте:

- не остались ли stale test VM;
- жив ли сам daemon Multipass;
- видны ли mounted folders внутри guest.

`agsekit doctor` умеет обнаруживать как минимум один известный stale-mount кейс.

## Ansible playbook падает в progress mode

Свежие версии `agsekit` буферизуют скрытый Ansible output и печатают последние строки при ошибке. Если нужен полный play output, перезапустите с `--debug`.

## Mount выглядит пустым внутри VM

Это может быть проблемой Multipass mount, а не конфига. Проверьте:

- `agsekit status`
- `multipass info <vm>`
- `agsekit doctor`

## Agent run падает из-за сети

Проверьте:

- не включены ли одновременно effective `proxychains` и `http_proxy`;
- достижим ли upstream proxy;
- не конфликтуют ли локальные SSH port forwards.

## Заметки для macOS host

- установка Multipass идёт через Homebrew;
- Linux-only интеграция с `systemd` пропускается.

## См. также

- [Known issues](known-issues.md)
- [doctor](commands/doctor.md)
- [Сеть](networking.md)
