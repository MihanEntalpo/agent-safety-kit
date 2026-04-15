# Documentation

This directory contains the user documentation for `agsekit`.

## Where to Start

- [Getting started](getting-started.md)
- [Configuration](configuration.md)
- [Supported agents](agents.md)
- [Architecture](architecture.md)
- [Networking and proxies](networking.md)
- [Backups](backups.md)
- [Troubleshooting](troubleshooting.md)
- [Practical how-to](how-to.md)
- [Known issues and limitations](known-issues.md)

## Command Reference

- [Command index](commands/README.md)
  - [prepare](commands/prepare.md)
  - [up](commands/up.md)
  - [create-vm / create-vms](commands/create-vm.md)
  - [install-agents](commands/install-agents.md)
  - [run](commands/run.md)
  - [mount / umount / addmount / removemount](commands/mount.md)
  - [status](commands/status.md)
  - [doctor](commands/doctor.md)
  - [systemd](commands/systemd.md)
  - [VM lifecycle](commands/vm-lifecycle.md)
  - [Networking commands](commands/networking.md)
  - [Backup commands](commands/backups.md)

## Languages

- [Русская документация](../docs-ru/README.md)

The CLI uses the system locale where possible. You can override behavior through `AGSEKIT_LANG`, for example `AGSEKIT_LANG=ru agsekit --help`.

## See Also

- [README.md](../README.md)
- [Project philosophy](../philosophy.md)
