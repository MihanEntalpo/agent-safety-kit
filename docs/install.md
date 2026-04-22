# Installation

## Contents

- [Linux](#linux)
- [macOS](#macos)
- [Windows](#windows)

## Linux

### Requirements:

* Deb-based and Arch-based distributions are supported
* WSL is not supported. Use a regular Linux host or native Windows PowerShell.
* The repository must have snapd; Multipass is installed through it.
* If you have an unsupported distribution, or no snapd, simply install Multipass manually in the system using any method available to you. That is enough for operation.

### Installation:

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

## macOS

### Requirements:

* macOS 13+ is the primary supported workflow, Homebrew is required
* If you have an older OS and use `agsekit prepare`, it installs the pinned legacy Multipass 1.14.1 cask through Homebrew
* If you install Multipass manually on an older OS, use an older Multipass; version 1.14.1 works on older macOS versions
* If you do not have Homebrew but can install Multipass some other way, that is enough for operation

### Installation:

* Install Homebrew; if you cannot, install Multipass in any convenient way
* If you have an old system (<13), `agsekit prepare` will use Multipass 1.14.1 when installing through Homebrew

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

## Windows

### Requirements

* Native Windows PowerShell is supported for installation and host-side tooling.
* Python 3.9+ is required. The installer checks for it and asks you to install Python first if it is missing.
* Multipass for Windows must be installed: https://canonical.com/multipass/install
* `agsekit prepare` can install MSYS2 through `winget` and then install `rsync` and `openssh` through MSYS2 `pacman`.
* Ansible-based provisioning commands (`up`, `create-vm`, `create-vms`, `install-agents`) are not available on native Windows because upstream Ansible does not support Windows control nodes.

### Installation

* Install Python 3.9+.
* Install Multipass for Windows.
* Open PowerShell.

**1. Automatically:**

The script at the link creates a venv, installs agsekit, creates an `agsekit.cmd` wrapper, and adds it to the user PATH.

```powershell
irm https://agsekit.org/install.ps1 | iex
```

The installer refreshes `PATH` in the current PowerShell session from Machine+User PATH. If another terminal still does not see `agsekit`, run the refresh command printed by the installer.

After installation, run:

```powershell
agsekit prepare
```

If MSYS2 or required MSYS2 packages are missing, `prepare` will ask before installing them. The default answer is yes.

To provision VMs and install agents after that, switch to a Linux or macOS host.

**2. Manually:**

Create a venv and install agsekit:

```powershell
$InstallRoot = "$env:USERPROFILE\.local\share\agsekit"
py -3 -m venv "$InstallRoot\venv"
& "$InstallRoot\venv\Scripts\python.exe" -m pip install -U pip agsekit
```

Create a command wrapper:

```powershell
$BinDir = "$env:USERPROFILE\.local\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Set-Content -Path "$BinDir\agsekit.cmd" -Value "@echo off`r`n`"$InstallRoot\venv\Scripts\agsekit.exe`" %*`r`n" -Encoding ASCII
```

Add the wrapper directory to user PATH:

```powershell
$CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not (($CurrentPath -split ";") -contains $BinDir)) {
    $NewPath = if ([string]::IsNullOrEmpty($CurrentPath)) { $BinDir } else { "$CurrentPath;$BinDir" }
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
}
```

Prepare host dependencies:

```powershell
agsekit prepare
```

For `up`, `create-vm`, `create-vms`, and `install-agents`, use Linux or macOS.
