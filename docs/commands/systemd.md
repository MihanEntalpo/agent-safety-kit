# `systemd`

## Contents

- [Purpose](#purpose)
- [Deprecated Alias](#deprecated-alias)
- [Platform Notes](#platform-notes)

## Purpose

`systemd` is now a deprecated alias for [`daemon`](daemon.md).

## Deprecated Alias

```bash
agsekit systemd install [--config <path>] [--debug]
agsekit systemd uninstall [--debug]
agsekit systemd start [--debug]
agsekit systemd stop [--debug]
agsekit systemd restart [--debug]
agsekit systemd status [--debug]
```

Each command prints a warning and then runs the matching `agsekit daemon ...` command.

## Platform Notes

- On Linux, `agsekit daemon` uses `systemd`.
- On macOS, `agsekit daemon` uses `launchd`.
- On Windows, `agsekit daemon` is not implemented yet.

## See Also

- [daemon](daemon.md)
- [up](up.md)
- [Networking commands](networking.md)
