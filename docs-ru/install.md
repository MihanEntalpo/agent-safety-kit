# Установка

## Содержание

- [Linux](#linux)
- [MacOS](#macos)
- [Windows](#windows)

## Linux

### Требования:

* Поддерживаются Deb-based и Arch-based дистрибутивы
* WSL не поддерживается. Используйте обычный Linux-хост или native Windows PowerShell.
* В репозитории должен быть snapd, через него ставится multipass.
* Если у вас неподдерживаемый дистрибутив, или нет snapd - просто установите в системе multipass доступным вам способом вручную, этого достаточно для работы.

### Установка:

* Установите python3.9 любым удобным вам способом
* Если у вас не Deb/Arch-based дистрибутив, и/или нет snapd, установите multipass вручную

**1) Автоматически:**

Скрипт по ссылке создаёт venv, ставит agsekit, добавляет его в PATH

```shell
curl -fsSL https://agsekit.org/install.sh | sh 
```

Перезапускаем shell:
```shell
$SHELL
```

**2) Вручную:**

Создаём venv и ставим agsekit:

```shell
INSTALL_ROOT="$HOME/.local/share/agsekit" && \
python -m venv "$INSTALL_ROOT/venv" && \
"$INSTALL_ROOT/venv/bin/python" -m pip install -U agsekit pip && \
mkdir -p "$HOME/.local/bin" && \
ln -s "$INSTALL_ROOT/venv/bin/agsekit" "$HOME/.local/bin"
```

Добавляем папку ~/.local/bin в PATH:
(добавляет только в те файлы, что существуют, и где ещё нет такой строки)

```shell
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

for FILE in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc" "$HOME/.zprofile"; do
    if [ -f "$FILE" ] && ! grep -Fxq "$PATH_LINE" "$FILE"; then
      printf '\n%s\n' "$PATH_LINE" >> "$FILE"
    fi
done
```

## MacOS

### Требования:

* Основной поддерживаемый сценарий - MacOs 13+, необходим HomeBrew
* Если у вас более старая ОС и вы используете `agsekit prepare`, он поставит зафиксированную legacy cask Multipass 1.14.1 через Homebrew
* Если вы ставите Multipass вручную на старой ОС, используйте более старый Multipass; версия 1.14.1 работает на более старых MacOs
* Если у вас нет HomeBrew, но вы можете как-то иначе установить multipass, этого достаточно для работы

### Установка:

* Установите HomeBrew, если не можете, установите любым удобным способом multipass
* Если у вас старая система (<13), `agsekit prepare` при установке через Homebrew будет использовать Multipass 1.14.1


**1) Автоматически:**

Скрипт по ссылке создаёт venv, ставит agsekit, добавляет его в PATH

```shell
curl -fsSL https://agsekit.org/install.sh | sh 
```

Перезапускаем shell:
```shell
$SHELL
```

**2) Вручную:**

Создаём venv и ставим agsekit:

```shell
INSTALL_ROOT="$HOME/.local/share/agsekit" && \
python -m venv "$INSTALL_ROOT/venv" && \
"$INSTALL_ROOT/venv/bin/python" -m pip install -U agsekit pip && \
mkdir -p "$HOME/.local/bin" && \
ln -s "$INSTALL_ROOT/venv/bin/agsekit" "$HOME/.local/bin"
```

Добавляем папку ~/.local/bin в PATH:
(добавляет только в те файлы, что существуют, и где ещё нет такой строки)

```shell
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

for FILE in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc" "$HOME/.zprofile"; do
    if [ -f "$FILE" ] && ! grep -Fxq "$PATH_LINE" "$FILE"; then
      printf '\n%s\n' "$PATH_LINE" >> "$FILE"
    fi
done
```

## Windows

### Требования

* Native Windows PowerShell поддерживается для установки и хостовых утилит.
* Нужен Python 3.9+. Установщик проверяет его наличие и попросит сначала установить Python, если его нет.
* Нужно установить Multipass for Windows: https://canonical.com/multipass/install
* `agsekit prepare` умеет поставить MSYS2 через `winget`, а затем `rsync` и `openssh` через MSYS2 `pacman`.
* Команды с Ansible-подготовкой (`up`, `create-vm`, `create-vms`, `install-agents`) на native Windows недоступны, потому что upstream Ansible не поддерживает Windows как control node.

### Установка

* Установите Python 3.9+.
* Установите Multipass for Windows.
* Откройте PowerShell.

**1) Автоматически:**

Скрипт по ссылке создаёт venv, ставит agsekit, создаёт wrapper `agsekit.cmd` и добавляет его в пользовательский PATH.

```powershell
irm https://agsekit.org/install.ps1 | iex
```

Установщик обновляет `PATH` в текущей PowerShell-сессии из Machine+User PATH. Если другой терминал всё ещё не видит `agsekit`, выполните команду обновления PATH, которую напечатает установщик.

После установки запустите:

```powershell
agsekit prepare
```

Если MSYS2 или нужных MSYS2-пакетов нет, `prepare` спросит перед установкой. Ответ по умолчанию - yes.

Чтобы после этого поднимать VM и ставить агентов, используйте Linux или macOS как хост.

**2) Вручную:**

Создаём venv и ставим agsekit:

```powershell
$InstallRoot = "$env:USERPROFILE\.local\share\agsekit"
py -3 -m venv "$InstallRoot\venv"
& "$InstallRoot\venv\Scripts\python.exe" -m pip install -U pip agsekit
```

Создаём command wrapper:

```powershell
$BinDir = "$env:USERPROFILE\.local\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Set-Content -Path "$BinDir\agsekit.cmd" -Value "@echo off`r`n`"$InstallRoot\venv\Scripts\agsekit.exe`" %*`r`n" -Encoding ASCII
```

Добавляем wrapper-каталог в пользовательский PATH:

```powershell
$CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not (($CurrentPath -split ";") -contains $BinDir)) {
    $NewPath = if ([string]::IsNullOrEmpty($CurrentPath)) { $BinDir } else { "$CurrentPath;$BinDir" }
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
}
```

Готовим host-зависимости:

```powershell
agsekit prepare
```

Для `up`, `create-vm`, `create-vms` и `install-agents` используйте Linux или macOS.
