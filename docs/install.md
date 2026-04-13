# Installation

### Linux

#### Requirements:

* Deb-based and Arch-based distributions are supported
* The repository must have snapd; Multipass is installed through it.
* If you have an unsupported distribution, or no snapd, simply install Multipass manually in the system using any method available to you. That is enough for operation.

#### Installation:

* Install python3.9 in any convenient way
* If you do not have a Deb/Arch-based distribution and/or snapd, install Multipass manually

**1. Automatically:**

The script at the link creates a venv, installs agsekit, and adds it to PATH

```shell
curl -fsSL https://agsekit.org/install.sh | sh
```

Restart the shell:

```shell
$SHELL
```

**2. Manually:**

Create a venv and install agsekit:

```shell
INSTALL_ROOT="$HOME/.local/share/agsekit" && \
python -m venv "$INSTALL_ROOT/venv" && \
"$INSTALL_ROOT/venv/bin/python" -m pip install -U agsekit pip && \
mkdir -p "$HOME/.local/bin" && \
ln -s "$INSTALL_ROOT/venv/bin/agsekit" "$HOME/.local/bin"
```

Add the ~/.local/bin folder to PATH:
(adds only to files that exist and do not yet contain this line)

```shell
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

for FILE in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc" "$HOME/.zprofile"; do
    if [ -f "$FILE" ] && ! grep -Fxq "$PATH_LINE" "$FILE"; then
      printf '\n%s\n' "$PATH_LINE" >> "$FILE"
    fi
done
```

### macOS

#### Requirements:

* macOS 13+ is supported, Homebrew is required
* If you have an older OS, you need to manually install an older Multipass (version 1.14.1 works on older macOS versions)
* If you do not have Homebrew but can install Multipass some other way, that is enough for operation

#### Installation:

* Install Homebrew; if you cannot, install Multipass in any convenient way
* If you have an old system (<13), install an old Multipass (1.14.1)

**1. Automatically:**

The script at the link creates a venv, installs agsekit, and adds it to PATH

```shell
curl -fsSL https://agsekit.org/install.sh | sh
```

Restart the shell:

```shell
$SHELL
```

**2. Manually:**

Create a venv and install agsekit:

```shell
INSTALL_ROOT="$HOME/.local/share/agsekit" && \
python -m venv "$INSTALL_ROOT/venv" && \
"$INSTALL_ROOT/venv/bin/python" -m pip install -U agsekit pip && \
mkdir -p "$HOME/.local/bin" && \
ln -s "$INSTALL_ROOT/venv/bin/agsekit" "$HOME/.local/bin"
```

Add the ~/.local/bin folder to PATH:
(adds only to files that exist and do not yet contain this line)

```shell
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

for FILE in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc" "$HOME/.zprofile"; do
    if [ -f "$FILE" ] && ! grep -Fxq "$PATH_LINE" "$FILE"; then
      printf '\n%s\n' "$PATH_LINE" >> "$FILE"
    fi
done
```

### Windows WSL

#### Requirements

* For now, only through WSL (full Windows support is planned for the future)
* Multipass must be installed in the main system (it will not work inside WSL)

#### Installation

* Install the regular Windows version of Multipass: https://canonical.com/multipass/download/windows
* If you have Windows Home, also install VirtualBox: https://www.virtualbox.org/wiki/Downloads
* Install WSL
* Start a WSL session and install Python 3.9+ there
* After that, run all commands in WSL, and agsekit will work only there as well.

**1. Automatically:**

The script at the link creates a venv, installs agsekit, and adds it to PATH

```shell
curl -fsSL https://agsekit.org/install.sh | sh
```

Restart the shell:

```shell
$SHELL
```

**2. Manually:**

Create a venv and install agsekit:

```shell
INSTALL_ROOT="$HOME/.local/share/agsekit" && \
python -m venv "$INSTALL_ROOT/venv" && \
"$INSTALL_ROOT/venv/bin/python" -m pip install -U agsekit pip && \
mkdir -p "$HOME/.local/bin" && \
ln -s "$INSTALL_ROOT/venv/bin/agsekit" "$HOME/.local/bin"
```

Add the ~/.local/bin folder to PATH:
(adds only to files that exist and do not yet contain this line)

```shell
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

for FILE in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc" "$HOME/.zprofile"; do
    if [ -f "$FILE" ] && ! grep -Fxq "$PATH_LINE" "$FILE"; then
      printf '\n%s\n' "$PATH_LINE" >> "$FILE"
    fi
done
```
