# `daemon`

## Contents

- [Purpose](#purpose)
- [Commands](#commands)
- [Platform Support](#platform-support)
- [`install`](#install)
- [`status`](#status)
- [Relation to `up` and `down`](#relation-to-up-and-down)
- [Deprecated Alias](#deprecated-alias)

## Purpose

Manage background services, including the service that keeps `agsekit portforward` running.

Platform backend:

- Linux: user-level `systemd`
- macOS: user-level `launchd`
- Windows: not implemented yet

## Commands

```bash
agsekit daemon install [--config <path>] [--debug]
agsekit daemon uninstall [--debug]
agsekit daemon start [--debug]
agsekit daemon stop [--debug]
agsekit daemon restart [--debug]
agsekit daemon status [--debug]
```

## Platform Support

- Linux: implemented via `systemd`
- macOS: implemented via `launchd`
- Windows: the command prints a warning and does nothing

## `install`

Writes the daemon configuration for the current platform, registers background services, and starts them.

On Linux:

- writes `systemd.env`
- links the bundled user unit
- reloads `systemd`
- restarts and enables the service

On macOS:

- writes a user `LaunchAgent`
- stores daemon logs in:
  - `~/Library/Logs/agsekit/daemon.stdout.log`
  - `~/Library/Logs/agsekit/daemon.stderr.log`
- bootstraps and starts the `launchd` job

In both cases, the daemon stores the absolute path to the current `agsekit` CLI, and `portforward` reuses that same installation for child `ssh` tunnel processes instead of depending on `PATH`.

## `status`

The output is platform-specific.

On Linux, it shows the linked unit, service state, and recent `journalctl` lines.

On macOS, it shows the plist path, loaded/enabled state, PID, last exit status, and tails of the stdout/stderr log files.

## Relation to `up` and `down`

On supported platforms, `agsekit up` automatically installs or updates the daemon after the VM and agent setup stages.

`agsekit down` also tries to stop daemon-managed services before shutting down VMs.

## Deprecated Alias

`agsekit systemd ...` remains available as a deprecated alias. It prints a warning and then runs the matching `agsekit daemon ...` command.

## See Also

- [up](up.md)
- [VM lifecycle](vm-lifecycle.md)
- [Networking commands](networking.md)
- [systemd](systemd.md)
