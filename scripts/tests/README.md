# Dangerous Developer Cleanup Scripts

This directory contains cleanup scripts for physical developer machines used to
test `scripts/install/install.sh`, `agsekit prepare`, and `agsekit up`.

These scripts are intentionally dangerous. They remove host packages, Homebrew
packages, symlinks, and the per-user `agsekit` virtual environment created by
the installer. Do not run them on a primary workstation unless you are prepared
to reinstall tooling manually.

Every script prints the exact category of changes it intends to make and then
requires the user to type exactly `yes`. Any other answer aborts without making
changes.

## Scripts

- `dangerous_clean_debian.sh` cleans a Debian or Ubuntu host.
- `dangerous_clean_wsl.sh` cleans a Debian or Ubuntu WSL environment.
- `dangerous_clean_macos.sh` cleans a macOS host.
- `dangerous_clean_arch.sh` cleans an Arch Linux host.
- `dangerous_clean_common.sh` contains shared helper functions and is not meant
  to be executed directly.

## What They Remove

### Debian and Ubuntu

`dangerous_clean_debian.sh` removes:

- the snap package `multipass`, if installed;
- `agsekit` only when it matches the `scripts/install/install.sh` layout;
- apt packages used by `agsekit prepare`, but only when they are marked as
  auto-installed dependencies:
  - `snapd`
  - `qemu-kvm`
  - `libvirt-daemon-system`
  - `libvirt-clients`
  - `bridge-utils`
  - `openssh-client`
  - `rsync`

Packages marked as manually installed by apt are kept.

### WSL

`dangerous_clean_wsl.sh` removes:

- apt packages used by `agsekit prepare`, using the same auto-installed-only
  rule as the Debian script;
- the WSL-side `~/.local/bin/multipass` symlink created by `scripts/install/install.sh`,
  but only if it points to a Windows `multipass.exe`;
- `agsekit` only when it matches the `scripts/install/install.sh` layout.

It does not remove Multipass from Windows.

### macOS

`dangerous_clean_macos.sh` removes:

- Homebrew formula `multipass`, if installed;
- Homebrew cask `multipass`, if installed;
- Homebrew formula `rsync`, if installed;
- `agsekit` only when it matches the `scripts/install/install.sh` layout.

### Arch Linux

`dangerous_clean_arch.sh` removes packages used by `agsekit prepare`, but only
when pacman reports that they were installed as dependencies:

- `multipass`
- `libvirt`
- `dnsmasq`
- `qemu-base`
- `openssh`
- `rsync`

Packages marked as explicitly installed by pacman are kept.

## `agsekit` Installer Cleanup

All scripts check whether `agsekit` is visible in `PATH`.

If it is visible and matches the layout created by `scripts/install/install.sh`, the
script removes:

- the package from `~/.local/share/agsekit/venv` with `pip uninstall -y agsekit`;
- the symlink `~/.local/bin/agsekit`;
- the virtual environment `~/.local/share/agsekit/venv`.

The scripts do not remove arbitrary `agsekit` binaries, arbitrary virtual
environments, or non-symlink files at `~/.local/bin/agsekit`.

## Usage

Run the script for the current host:

```sh
scripts/tests/dangerous_clean_debian.sh
scripts/tests/dangerous_clean_wsl.sh
scripts/tests/dangerous_clean_macos.sh
scripts/tests/dangerous_clean_arch.sh
```

Then reinstall and prepare the environment under test, for example:

```sh
sh scripts/install/install.sh
agsekit prepare
```

## Safety Notes

- These scripts are for project developers only.
- They are not part of the user-facing installation flow.
- They may call `sudo` on Linux.
- They may call Homebrew uninstall commands on macOS.
- They intentionally do not edit shell startup files or remove the PATH line
  added by `scripts/install/install.sh`.
- They intentionally avoid removing packages that the package manager says were
  manually or explicitly installed.
