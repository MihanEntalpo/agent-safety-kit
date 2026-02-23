# TODO: Missing Integration Tests

Цель файла: зафиксировать интеграционные тесты, которые **стоит добавить**, но которых сейчас нет.

## Текущее состояние

- Сейчас в `tests/integration/` есть:
  - `test_prepare_host.py`
  - `test_vm_lifecycle.py`
  - `test_mounts_lifecycle.py`
  - `test_backups_lifecycle.py`
- Остальные крупные сценарии по-прежнему покрыты в основном unit/functional-тестами с моками.

## P0 (критично добавить в первую очередь)

### VM lifecycle (`create-vm`, `create-vms`, `start-vm`, `stop-vm`, `destroy-vm`)

- [v] `create-vm` на чистой системе: VM реально создаётся в Multipass и переходит в `Running`.
- [v] `create-vm` повторный запуск: корректная идемпотентность (без падения, с ожидаемым сообщением).
- [v] `create-vm` при mismatch ресурсов: корректный detect mismatch без разрушения существующей VM.
- [v] `create-vms`: создание нескольких VM из конфига.
- [v] `stop-vm` + `start-vm`: проверка реальной смены состояния VM.
- [v] `destroy-vm` одной VM: реально удаляет инстанс.
- [v] `destroy-vm --all`: удаляет все VM из конфига.

### Mounts (`mount`, `umount`, `addmount`, `removemount`)

- [v] `mount` одного источника: путь реально виден внутри VM.
- [v] `mount --all`: монтируются все записи из конфига.
- [v] `umount`: mount реально исчезает из VM.
- [v] `addmount --mount`: запись добавляется в YAML и сразу монтируется.
- [v] `removemount`: сначала успешный umount, потом удаление записи из YAML.
- [v] Разрешение относительного/вложенного пути (`mount`/`umount`) на реальной FS.

### Backups (`backup-once`, `backup-repeated*`, `backup-clean`)

- [v] `backup-once`: создаёт snapshot, следующий snapshot использует hardlinks, при отсутствии изменений новый snapshot не создаётся.
- [v] `backup-repeated`: делает периодические снапшоты и корректно завершается по SIGINT.
- [v] `backup-repeated-mount`: берёт параметры mount из конфига и реально бэкапит.
- [v] `backup-repeated-all`: поднимает циклы по всем mount.
- [v] `backup-clean tail`: оставляет последние N снапшотов.
- [v] `backup-clean thin`: корректно прореживает историю по thin-алгоритму.

### Agent flow (`install-agents`, `run`)

- [ ] `install-agents` (минимум один тип, например `qwen`) в реальную VM: бинарник реально появляется и запускается.
- [ ] `install-agents --all-agents`: установка всех агентов из конфига.
- [ ] `run` в mounted-папке: агент стартует внутри VM в ожидаемом `cwd`.
- [ ] `run` с включёнными бэкапами: создаётся initial snapshot и стартует фоновый backup-loop.
- [ ] `run --disable-backups`: агент стартует без backup-loop.

### Connectivity (`ssh`, `shell`, `portforward`, `status`)

- [ ] `ssh` подключается в VM с ключами из `~/.config/agsekit/ssh`.
- [ ] `shell` реально открывает сессию в VM (smoke через неинтерактивную команду-эквивалент).
- [ ] `portforward`: поднимает SSH-туннели и восстанавливает их после падения дочернего процесса.
- [ ] `status`: end-to-end выводит реальные VM state/resources/mounts/backup timestamps/agent processes.

## P1 (важно добавить после P0)

### Systemd mode

- [ ] `systemd install`: ставит unit, записывает `systemd.env`, сервис реально стартует.
- [ ] `systemd uninstall`: корректно останавливает/удаляет unit.

### Proxychains + forwarding

- [ ] `run --proxychains ...`: агент реально стартует через proxychains-wrapper.
- [ ] `install-agents --proxychains ...`: установка агента проходит через proxychains.
- [ ] VM `port-forwarding` с `local`/`remote`/`socks5`: проверка фактической маршрутизации трафика.

### Bundles during VM prepare

- [ ] `create-vm` с `install: [python, nodejs, rust, docker]`: после prepare в VM доступны соответствующие инструменты.
- [ ] `list-bundles` в связке с create-vm: smoke, что заявленные bundles действительно применимы.

## P2 (дополнительно, для устойчивости)

### Config UX (`config-example`, `config-gen`)

- [ ] `config-example`: реальное копирование/skip без повреждения существующего файла.
- [ ] `config-gen`: интерактивная генерация валидного конфига и последующее успешное `create-vm`.

### Maintenance commands (`pip-upgrade`, `version`)

- [ ] `pip-upgrade`: в отдельном venv проверка ветки "обновилось" и "уже latest" (без моков, на локальном индексе/подготовленном артефакте).
- [ ] `version`: smoke в установленном окружении (валидность installed/project версий).

### Interactive mode

- [ ] `agsekit` в TTY: сквозной сценарий выбора команды из меню и успешного выполнения (через pexpect/pty harness).
- [ ] fallback в интерактивный режим при неполных аргументах.

## Notes по запуску

- Все тесты этого файла предполагаются под маркером `host_integration`.
- Для CI/облака нужен отдельный профиль запуска (из-за изменений хост-системы и требований к sudo/snapd/Multipass).
- Для изоляции интеграционных тестов желательно использовать уникальные имена VM и временные директории, а также обязательную cleanup-фазу.
