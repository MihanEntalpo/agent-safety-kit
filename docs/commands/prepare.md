# `prepare`

## Purpose

Prepare the host machine for `agsekit` workflows.

## Command

```bash
agsekit prepare [--config <path>] [--debug]
```

## What It Does

- installs required host-side dependencies, especially Multipass;
- creates or reuses the host SSH keypair for VM access;
- reads `global.ssh_keys_folder` from config when available.

## Platform Notes

- Linux: supports Debian-based package installs and Arch-based package installs.
- macOS: installs Multipass via Homebrew.
- Windows: not a first-class workflow yet.

## Examples

```bash
agsekit prepare
agsekit prepare --debug
agsekit prepare --config ~/.config/agsekit/config.yaml
```

## See Also

- [up](up.md)
- [Configuration](../configuration.md)
