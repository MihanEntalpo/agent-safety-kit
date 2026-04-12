# Установка

### Linux

#### Требования:

* Поддерживаются Deb-based и Arch-based дистрибутивы
* В репозитории должен быть snapd, через него ставится multipass.
* Если у вас неподдерживаемый дистрибутив, или нет snapd - просто установите в системе multipass доступным вам способом вручную, этого достаточно для работы.

#### Установка:

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

### MacOS

#### Требования:

* Поддерживается MacOs 13+, необходим HomeBrew
* Если у вас более старая ОС, нужно вручную поставить более старый mutlipass (Версия 1.14.1 работает на более старых MacOs)
* Если у вас нет HomeBrew, но вы можете как-то иначе установить multipass, этого достаточно для работы

#### Установка:

* Установите HomeBrew, если не можете, установите любым удобным способом multipass
* Если у вас старая система (<13), установите старый multipass (1.14.1)


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

### Windows WSL

#### Требования

* Пока только через WSL (Полноценная поддержка Windows планируется в будущем)
* mutlipass нужно установить в основной системе (внутри WSL он работать не будет)

#### Установка

* Установите обычную Windows-версию multipass https://canonical.com/multipass/download/windows
* Если у вас Windows Home, то также установите VirtualBox https://www.virtualbox.org/wiki/Downloads 
* Установите WSL
* Запустите сеанс WSL, установите там python 3.9+
* Дальше все команды выполняем в WSL, и работать agsekit будет тоже только там.

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

