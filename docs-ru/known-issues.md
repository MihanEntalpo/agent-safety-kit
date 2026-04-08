# Known Issues

На этой странице собраны текущие ограничения, а не уже исправленные баги.

## Текущие ограничения

- Windows host support пока не является first-class workflow.
- Linux-only интеграция с `systemd` пока не имеет нативной macOS-замены на `launchd`.
- Изоляция guest полезна, но mounted folders всё равно writable из VM.
- Большие installers и сборки из исходников могут быть медленными на маленьких VM.

## Операционные оговорки

- mount-поведение Multipass может ломаться независимо от `agsekit`.
- конкретные proxy-настройки зависят от возможностей самого agent CLI.
- backup policy защищает файлы, но не защищает от внешних side effects вроде изменений в БД или сетевых действий.

## См. также

- [Troubleshooting](troubleshooting.md)
- [Философия проекта](../philosophy-ru.md)
