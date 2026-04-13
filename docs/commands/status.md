# `status`

## Purpose

Show a summary operational report for the configured environment.

## Command

```bash
agsekit status [--config <path>] [--debug]
```

## What It Shows

- config path
- VM states
- configured and real VM resources
- `portforward` process state
- information about mounts and backup snapshots
- configured and installed agents by VM
- current agent processes and their working directories

## Example

```bash
agsekit status
agsekit status --debug
```

## See Also

- [run](run.md)
- [VM lifecycle](vm-lifecycle.md)
- [Networking commands](networking.md)
