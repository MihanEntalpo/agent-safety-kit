# `prepare`

## Contents

- [Purpose](#purpose)
- [Command](#command)
- [What It Does](#what-it-does)
- [Platform Notes](#platform-notes)
- [Examples](#examples)

## Purpose

Prepare the host machine for the `agsekit` workflow.

## Command

```bash
agsekit prepare [--config <path>] [--debug]
```

## What It Does

- checks required host-side dependencies;
- if `multipass` is already in `PATH`, it does not install Multipass or `snapd`;
- if host packages are needed, installs only the missing ones;
- checks for `ssh-keygen` and installs the OpenSSH client package on supported Linux when needed;
- checks for `rsync` and installs it through the Linux package manager, Homebrew on macOS, or MSYS2 on native Windows when needed;
- on native Windows, if MSYS2 tools are missing, asks before installing MSYS2 through `winget` and `rsync`/`openssh` through MSYS2 `pacman`;
- adds the MSYS2 binary directory to the current process and the user `PATH` on native Windows;
- creates or reuses a host SSH keypair for VM access;

## Platform Notes

- Linux: Debian-based and Arch-based package installations are supported; on Debian-based systems `snapd` is installed only when `multipass` is missing
- macOS: Multipass and `rsync` are installed through Homebrew, only when missing.
- Windows host: native Windows can prepare MSYS2 host tools (`rsync` and `openssh`); Multipass for Windows must be installed separately.
- WSL is not supported. Use a regular Linux host or native Windows PowerShell.

## Examples

```bash
agsekit prepare
agsekit prepare --debug
agsekit prepare --config ~/.config/agsekit/config.yaml
```

## See Also

- [up](up.md)
- [Configuration](../configuration.md)
