# Различные технчиеские скрипты agsekit

## install/install.sh - универсальный скрипт установки для `curl | bash`

Работает в:

* Linux
  * debian
  * arch
* MacOS
* WSL (windows linux subsystem)

Что делает:

* Создаёт venv
* Устанавливает в него agsekit
* Добавляет agsekit в PATH для запуска откуда угодно
* В WSL создаёт `~/.local/bin/multipass` как symlink на установленный в Windows `multipass.exe`
