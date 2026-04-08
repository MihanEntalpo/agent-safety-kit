# `doctor`

## Purpose

Diagnose known installation and runtime problems and offer safe repairs.

## Command

```bash
agsekit doctor [--config <path>] [-y] [--debug]
```

## Current Scope

The command currently focuses on known Multipass-related problems, especially stale or broken mount visibility cases.

## Behavior

- inspects configured mounts;
- checks whether host data appears unexpectedly empty inside the VM;
- can propose a Multipass daemon restart when that known issue is detected.

## Examples

```bash
agsekit doctor
agsekit doctor -y
agsekit doctor --debug
```

## See Also

- [Troubleshooting](../troubleshooting.md)
- [create-vm](create-vm.md)
