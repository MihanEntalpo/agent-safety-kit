# `prepare`

## Purpose

Prepare the host machine for the `agsekit` workflow.

## Command

```bash
agsekit prepare [--config <path>] [--debug]
```

## What It Does

- installs required host-side dependencies, primarily Multipass;
- creates or reuses a host SSH keypair for VM access;

## Platform Notes

- Linux: Debian-based and Arch-based package installations are supported, uses snapd
- macOS: Multipass is installed through Homebrew.
- Windows: not a first-class workflow yet, so Multipass must be installed manually here

## Examples

```bash
agsekit prepare
agsekit prepare --debug
agsekit prepare --config ~/.config/agsekit/config.yaml
```

## See Also

- [up](up.md)
- [Configuration](../configuration.md)
