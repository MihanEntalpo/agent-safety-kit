# `create-vm` and `create-vms`

## Contents

- [Purpose](#purpose)
- [Commands](#commands)
- [What Happens](#what-happens)
- [Behavior for an Existing VM](#behavior-for-an-existing-vm)
- [Examples](#examples)

## Purpose

Create/configure Multipass VMs from the config and prepare them for agent work.

It is idempotent; after any VM configuration change (for example, adding new bundles to `vms.<vm_name>.install`) you can run this command again.

## Commands

```bash
agsekit create-vm <name> [--config <path>] [--debug]
agsekit create-vms [--config <path>] [--debug]
```

## What Happens

- `agsekit` checks whether the VM exists
- if there is no VM, it is created
- starts the VM if it was stopped
- synchronizes SSH keys and known_hosts through Multipass
- installs base packages through Ansible over SSH using the key from `global.ssh_keys_folder`
- installs software bundles (`vms.<vm_name>.install`) into the VM

## Behavior for an Existing VM

If the VM already exists, `agsekit` compares real and configured resources and reports differences. Automatic resizing of an existing VM is not supported yet.

## Examples

```bash
agsekit create-vms
agsekit create-vm agent-ubuntu
agsekit create-vm agent-ubuntu --debug
```

The `--debug` argument enables detailed output of the VM setup process.

## See Also

- [prepare](prepare.md)
- [VM lifecycle](vm-lifecycle.md)
- [Configuration](../configuration.md)
