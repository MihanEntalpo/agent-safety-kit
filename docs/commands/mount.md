# Mount Commands

## Covered Commands

```bash
agsekit mount --source-dir <path> [--config <path>] [--debug]
agsekit umount --source-dir <path> [--config <path>] [--debug]
agsekit addmount <path> [...] [--config <path>] [--mount] [-y] [--debug]
agsekit removemount [<path>] [--config <path>] [--vm <vm_name>] [-y] [--debug]
```

## `mount`

Mounts a configured host directory into its VM.

Useful forms:

```bash
agsekit mount --source-dir /path/to/project
agsekit mount --all
```

## `umount`

Unmounts a configured mount from its VM.

Useful forms:

```bash
agsekit umount --source-dir /path/to/project
agsekit umount --all
```

## `addmount`

Adds a mount entry to the YAML config and can optionally mount it immediately.

Typical fields controlled by the command:

- source path
- VM name
- VM path
- backup path
- backup interval
- max backups
- cleanup policy
- allowed agents

## `removemount`

Removes a mount entry from config. The CLI unmounts it first and preserves the config when unmounting fails.

## See Also

- [Configuration](../configuration.md)
- [Backups](../backups.md)
- [run](run.md)
