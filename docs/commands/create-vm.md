# `create-vm` and `create-vms`

## Purpose

Create Multipass VMs from config and prepare them for agent work.

## Commands

```bash
agsekit create-vm <name> [--config <path>] [--debug]
agsekit create-vms [--config <path>] [--debug]
```

## What Happens

- `agsekit` checks whether the VM already exists;
- launches missing VMs with the configured resources;
- starts the VM;
- synchronizes SSH access;
- installs base packages through Ansible.

## Existing VM Behavior

If a VM already exists, `agsekit` compares real and configured resources and reports differences. Resizing an existing VM is not handled automatically yet.

## Examples

```bash
agsekit create-vms
agsekit create-vm agent-ubuntu
agsekit create-vm agent-ubuntu --debug
```

## See Also

- [prepare](prepare.md)
- [VM lifecycle](vm-lifecycle.md)
- [Configuration](../configuration.md)
