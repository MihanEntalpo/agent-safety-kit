# `status`

## Purpose

Print a consolidated operational report for the configured environment.

## Command

```bash
agsekit status [--config <path>] [--debug]
```

## What It Shows

- config location
- VM states
- configured versus actual VM resources
- `portforward` process state
- mount and backup snapshot information
- configured and installed agents per VM
- currently running agent processes and their working directories

## Example

```bash
agsekit status
agsekit status --debug
```

## See Also

- [run](run.md)
- [VM lifecycle](vm-lifecycle.md)
- [Networking](networking.md)
