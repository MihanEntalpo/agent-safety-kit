# `systemd`

## Purpose

Manage the Linux-only user service that keeps `agsekit portforward` running in the background.

## Covered Commands

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
- macOS: command prints a warning and does nothing
- Windows: command prints a warning and does nothing

## `install`

Writes `systemd.env`, links the bundled user unit, reloads systemd, restarts the service, and enables it.

## `status`

Shows:

- bundled unit path
- linked user unit path
- installation state
- active/enabled state
- recent journal tail

## Relationship With `up`

On Linux, `agsekit up` can install/update this service automatically after VM and agent setup.

## See Also

- [up](up.md)
- [Networking commands](networking.md)
