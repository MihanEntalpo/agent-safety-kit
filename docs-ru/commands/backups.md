# Backup-команды

## Команды

```bash
agsekit backup-once --source-dir <path> --dest-dir <path> [...]
agsekit backup-repeated --source-dir <path> --dest-dir <path> [...]
agsekit backup-repeated-mount --mount <path> [--config <path>]
agsekit backup-repeated-all [--config <path>]
agsekit backup-clean <mount_source> [<keep>] [<method>] [--config <path>]
```

## `backup-once`

Создаёт один snapshot в целевом каталоге. Если относительно предыдущего снапшота ничего не изменилось, новый снапшот не создаётся.
С `--progress` на Linux в rsync передаются `--progress --info=progress2`; на macOS и Windows передаётся только `--progress`, чтобы сохранять совместимость со старыми bundled-версиями rsync.

## `backup-repeated`

Запускает бэкапы по таймеру и поддерживает режим пропуска первого запуска.

## `backup-repeated-mount`

Резолвит пути и policy из настроенной mount entry.

## `backup-repeated-all`

Запускает repeated backup loops для всех mount из конфига.

## `backup-clean`

Чистит старые снапшоты по policy `tail` или `thin`.

## См. также

- [Обзор бэкапов](../backups.md)
- [run](run.md)
