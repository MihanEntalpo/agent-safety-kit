# Architecture

`agsekit` is built around a "host plus VM" workflow.

## Main Components

- Host machine: stores the real project, backup directory, and YAML config.
- Multipass VM: runs Ubuntu and the agent process.
- Mount: exposes the host directory inside the VM.
- Backup loop: makes snapshots of the host directory while the agent is running.
- Port forwarding: keeps SSH tunnels alive if they are configured.
- Optional proxy layer: applies `proxychains` or `http_proxy` for installation and runtime.

## Execution Flow

1. The user describes VMs, mounts, and agents in YAML.
2. `agsekit` prepares the host and creates the VM.
3. The host directory is mounted into the selected VM.
4. The agent binary is installed inside the VM.
5. `agsekit run` launches the agent inside the VM and, if needed, starts repeated backups.
6. Network helpers are enabled on top of this when needed.

## Isolation Boundary

The host stores the canonical working tree and launches the VM. The agent does not run directly in the host shell. At the same time, the mounted project still remains writable from the guest VM, so the VM itself does not replace backups and version control.

## Backup Model

Backups are created on the host side, not inside the VM. Snapshots are created through `rsync` and hardlinks to save space when only part of the tree changes.

## Network Model

- `proxychains` wraps commands when SOCKS or a proxy-aware runtime is needed.
- `http_proxy` can be direct or upstream through a temporary `privoxy`.
- `portforward` keeps SSH forwards based on the config.

## See Also

- [Getting started](getting-started.md)
- [Configuration](configuration.md)
- [Networking](networking.md)
- [Backups](backups.md)
