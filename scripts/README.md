# Различные технчиеские скрипты agsekit

## install/install.sh - универсальный скрипт установки для `curl | bash`

Работает в:

* Linux
  * debian
  * arch
* MacOS

Что делает:

* Создаёт venv
* Устанавливает в него agsekit
* Добавляет agsekit в PATH для запуска откуда угодно

## install/install.ps1 - Windows-скрипт установки для PowerShell

Работает в native Windows PowerShell. WSL не поддерживается.

Что делает:

* Проверяет наличие Python 3.9+
* Создаёт venv
* Устанавливает в него agsekit
* Создаёт `agsekit.cmd`
* Добавляет wrapper-каталог в пользовательский PATH
