# `doctor`

## Purpose

Diagnose known installation and runtime problems and suggest safe fixes.

## Command

```bash
agsekit doctor [--config <path>] [-y] [--debug]
```

## Current Scope

Right now the command mostly focuses on known Multipass failures, especially stale or broken mount visibility.

## Behavior

- analyzes configured mounts;
- checks whether a non-empty host directory looks empty inside the VM;
- for a known error type, can suggest restarting the Multipass daemon.

## Examples

Run in interactive mode:

```bash
agsekit doctor
```

Run and agree to apply fixes:

```shell
agsekit doctor -y
```

Run with detailed diagnostic output:

```shell
agsekit doctor --debug
```

## See Also

- [Troubleshooting](../troubleshooting.md)
- [create-vm](create-vm.md)
