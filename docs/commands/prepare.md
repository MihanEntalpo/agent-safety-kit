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
- checks for `rsync` and installs it through the Linux package manager or Homebrew on macOS when needed;
- creates or reuses a host SSH keypair for VM access;

## Platform Notes

- Linux: Debian-based and Arch-based package installations are supported; on Debian-based systems `snapd` is installed only when `multipass` is missing
- macOS: Multipass and `rsync` are installed through Homebrew, only when missing.
- Windows host: currently only through WSL.
- WSL: `prepare` does not install `snapd` or Multipass inside WSL; Multipass must be installed in Windows and available as the `multipass` command inside WSL.

## Examples

```bash
agsekit prepare
agsekit prepare --debug
agsekit prepare --config ~/.config/agsekit/config.yaml
```

## See Also

- [up](up.md)
- [Configuration](../configuration.md)
