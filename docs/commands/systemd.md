# `systemd`

## Contents

- [Purpose](#purpose)
- [Commands](#commands)
- [Platform Support](#platform-support)
- [`install`](#install)
- [`status`](#status)
- [Relation to `up`](#relation-to-up)

## Purpose

Manage the Linux-only user service that keeps `agsekit portforward` running in the background.

## Commands

```bash
agsekit systemd install [--config <path>] [--debug]
agsekit systemd uninstall [--debug]
agsekit systemd start [--debug]
agsekit systemd stop [--debug]
agsekit systemd restart [--debug]
agsekit systemd status [--debug]
```

## Platform Support

- Linux: implemented
- macOS: the command prints a warning and does nothing
- Windows: the command prints a warning and does nothing

## `install`

Writes `systemd.env`, links the bundled user unit, reloads systemd, restarts the service, and enables it.

## `status`

Shows:

- path to bundled unit
- path to linked user unit
- installation state
- active/enabled state
- tail of recent journal entries

## Relation to `up`

On Linux, `agsekit up` can automatically install or update this service after the VM and agent setup stages.

## See Also

- [up](up.md)
- [Networking commands](networking.md)
