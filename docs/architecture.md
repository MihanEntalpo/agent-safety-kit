# Architecture

`agsekit` is built around a host-plus-VM workflow.

## Main Components

- Host machine: stores the real project directory, backup destination, and YAML config.
- Multipass VM: runs Ubuntu and hosts the agent process.
- Mount: exposes a host directory inside the VM.
- Backup loop: snapshots the host directory while the agent is running.
- Port forwarding: keeps SSH tunnels alive when configured.
- Optional proxy layer: applies `proxychains` or `http_proxy` rules for installation and runtime.

## Execution Flow

1. The user defines VMs, mounts, and agents in YAML.
2. `agsekit` prepares the host and creates the VMs.
3. A host directory is mounted into the target VM.
4. The selected agent binary is installed inside the VM.
5. `agsekit run` starts the agent inside the VM and can also start repeated backups.
6. Optional networking helpers are applied on top of that runtime.

## Isolation Boundary

The host keeps the canonical working tree and launches the VM. The agent does not execute directly on the host shell. The mounted project is still writable by the guest, so VM isolation is not a replacement for backups and version control.

## Backup Model

Backups are made on the host side, not inside the VM. Snapshots are created with `rsync` and hardlinks to minimize space usage when only part of the tree changes.

## Networking Model

- `proxychains` wraps commands when SOCKS or HTTP tunnel behavior is needed.
- `http_proxy` can be direct or upstream via temporary `privoxy`.
- `portforward` keeps SSH forwards alive based on config.

## See Also

- [Getting started](getting-started.md)
- [Configuration reference](configuration.md)
- [Networking](networking.md)
- [Backups](backups.md)
