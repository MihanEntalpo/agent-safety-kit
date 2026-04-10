# Бэкапы

Бэкапы это базовая часть workflow `agsekit`.

## Модель

- Снапшоты создаются на стороне хоста.
- Данные копируются через `rsync`.
- Неизменившиеся файлы hardlink'аются из предыдущего снапшота.
- Один каталог назначения защищён файловым lock, поэтому в него пишет только один backup writer.
- Флаги прогресса rsync зависят от ОС хоста: на Linux используется `--progress --info=progress2`, а на macOS и Windows для совместимости со старыми сборками rsync используется `--progress`.
- Если rsync печатает в progress output байты не в UTF-8, `agsekit` заменяет их и продолжает бэкап.

## Основные команды

- `backup-once`
- `backup-repeated`
- `backup-repeated-mount`
- `backup-repeated-all`
- `backup-clean`

## Во время `agsekit run`

Если для выбранного mount включены backups и не передан `--disable-backups`:

1. `agsekit` убеждается, что initial snapshot существует;
2. агент запускается внутри VM;
3. repeated backups продолжают работать в фоне всю сессию.

Если `agsekit run` запущен либо из отсутствующей папки проекта, либо из существующей папки вне настроенных mount, и пользователь соглашается на временную workdir внутри VM, mount не выбирается и бэкапы для этой сессии не запускаются.

## Политики очистки

- `tail`: оставить N последних снапшотов
- `thin`: плотная история рядом с текущим временем и всё более редкие старые снапшоты

## `.backupignore`

`agsekit` читает `.backupignore` внутри исходного дерева и прокидывает exclusion logic в `rsync`.

Пример:

```text
venv/
node_modules/
*.log
!logs/important.log
```

## См. также

- [Backup-команды](commands/backups.md)
- [Troubleshooting](troubleshooting.md)
- [Архитектура](architecture.md)
