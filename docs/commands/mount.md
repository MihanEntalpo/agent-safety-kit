# Mount Commands

## Commands

```bash
agsekit mount [SOURCE_DIR] [--all] [--config <path>] [--non-interactive] [--debug]
agsekit umount [SOURCE_DIR] [--all] [--config <path>] [--non-interactive] [--debug]
agsekit addmount [SOURCE_DIR] [TARGET_DIR] [BACKUP_DIR] [INTERVAL] [--vm <vm_name>] [--max-backups <count>] [--backup-clean-method tail|thin] [--mount] [--allowed-agents <a,b,c>] [-y] [--config <path>] [--non-interactive] [--debug]
agsekit removemount [SOURCE_DIR] [--vm <vm_name>] [-y] [--config <path>] [--non-interactive] [--debug]
```

Common arguments:

- `--config <path>` - path to the YAML config. If not specified, `CONFIG_PATH` or `~/.config/agsekit/config.yaml` is used.
- `--non-interactive` - disables interactive prompts. For `mount` and `umount` it currently has almost no effect on behavior, but for `addmount` and `removemount` it makes mandatory the parameters that otherwise could have been asked.
- `--debug` - prints executed commands and diagnostic output.

## `mount`

Mounts a host directory specified in the configuration into the corresponding VM.

Signature:

```bash
agsekit mount [SOURCE_DIR] [--all] [--config <path>] [--non-interactive] [--debug]
```

Arguments:

- `SOURCE_DIR` - path to a folder on the host. The command searches for a suitable `mounts[]` entry by `source`; you can specify the `source` itself or a subfolder inside it.
- `--all` - mount all entries from `mounts[]`.
- `--config <path>` - which YAML config to read.
- `--non-interactive` - common CLI flag; does not add separate prompts for this command.
- `--debug` - show Multipass commands and debug output.

Selection rules:

- `SOURCE_DIR` and `--all` cannot be specified together.
- If `SOURCE_DIR` is not specified and there is one mount in the config, it is used.
- If `SOURCE_DIR` is not specified and there are several mounts, the command asks to specify a path or `--all`.
- If the mount is already registered in Multipass, the command writes that and does not fail.

Examples:

```bash
agsekit mount /path/to/project
agsekit mount --all
```

## `umount`

Unmounts a configured mount from the VM.

Signature:

```bash
agsekit umount [SOURCE_DIR] [--all] [--config <path>] [--non-interactive] [--debug]
```

Arguments:

- `SOURCE_DIR` - path to a folder on the host. The command searches for a suitable `mounts[]` entry by `source`; you can specify the `source` itself or a subfolder inside it.
- `--all` - unmount all entries from `mounts[]`.
- `--config <path>` - which YAML config to read.
- `--non-interactive` - common CLI flag; does not add separate prompts for this command.
- `--debug` - show Multipass commands and debug output.

Selection rules are the same as for `mount`: `SOURCE_DIR` and `--all` conflict, one mount is selected automatically, and with several mounts a path or `--all` is needed.

Examples:

```bash
agsekit umount /path/to/project
agsekit umount --all
```

## `addmount`

Adds a mount entry to the YAML config and can optionally mount it immediately.

It has a convenient interactive mode; you can run simply:

```shell
agsekit addmount [SOURCE_DIR]
```

Signature:

```bash
agsekit addmount [SOURCE_DIR] [TARGET_DIR] [BACKUP_DIR] [INTERVAL] [--vm <vm_name>] [--max-backups <count>] [--backup-clean-method tail|thin] [--mount] [--allowed-agents <a,b,c>] [-y] [--config <path>] [--non-interactive] [--debug]
```

Positional arguments:

- `SOURCE_DIR` - host folder to add to `mounts[].source`. In interactive mode, if not specified, a prompt asks with the current folder as default. In non-interactive mode it is required.
- `TARGET_DIR` - path inside the VM for `mounts[].target`. If not specified, `/home/ubuntu/<SOURCE_DIR name>` is used.
- `BACKUP_DIR` - folder on the host for `mounts[].backup`. If not specified, `<SOURCE_DIR parent>/backups-<SOURCE_DIR name>` is used.
- `INTERVAL` - value of `mounts[].interval`, backup interval in minutes. If not specified, the default is `5`; in interactive mode a prompt asks for it.

Options:

- `--vm <vm_name>` - value of `mounts[].vm`, VM for the new entry. If the config has one VM, it is selected automatically. If there are several VMs and the flag is not specified, interactive mode will show a prompt, and non-interactive mode will select the first VM from the `vms` section.
- `--max-backups <count>` - value of `mounts[].max_backups`, how many snapshots to keep. Default: `100`; value must be positive.
- `--backup-clean-method tail|thin` - value of `mounts[].backup_clean_method`. Default: `thin`.
- `--mount` - immediately run `multipass mount` after saving the entry.
- `--allowed-agents <a,b,c>` - write `mounts[].allowed_agents`, comma-separated list of allowed agents. Names must exist in the `agents` section.
- `-y`, `--yes` - skip confirmation before changing the config. In non-interactive mode it is required, otherwise the command exits with an error at confirmation.
- `--config <path>` - which YAML config to modify.
- `--non-interactive` - disable prompts and use passed/default values.
- `--debug` - show debug output.

What is written to the config:

- `source`
- `vm`
- `target`
- `backup`
- `interval`
- `max_backups`
- `backup_clean_method`
- `allowed_agents`, if it was specified or selected interactively

Before writing, the command shows a summary, checks that there is no such `source + vm` yet, creates a timestamp backup of the YAML file next to the config, and saves the file while preserving comments.

If `--mount` was not passed, but the command is running interactively, after saving there will be a question: `Mount the folder immediately? [Y/n]`. The default answer is yes.

## `removemount`

Removes a mount entry from the config. The CLI first tries to unmount the mount and saves the config unchanged if unmounting failed.

Signature:

```bash
agsekit removemount [SOURCE_DIR] [--vm <vm_name>] [-y] [--config <path>] [--non-interactive] [--debug]
```

Arguments:

- `SOURCE_DIR` - `mounts[].source` that should be removed. Comparison is done by normalized absolute path. In interactive mode, if the path is not specified, the command offers to choose a mount from the list. In non-interactive mode the path is required.
- `--vm <vm_name>` - clarify the VM if there are several mount entries with the same `source` but different VMs.
- `-y`, `--yes` - skip confirmation before deletion. In non-interactive mode it is required, otherwise the command exits with an error at confirmation.
- `--config <path>` - which YAML config to modify.
- `--non-interactive` - disable mount selection prompt and confirmation prompt.
- `--debug` - show Multipass commands and debug output.

Selection rules:

- If `SOURCE_DIR` is found in exactly one entry, it is removed.
- If several entries with the same `SOURCE_DIR` are found, use `--vm <vm_name>`; in interactive mode you can choose the entry from a list.
- If `SOURCE_DIR` is not specified, interactive mode offers a choice from all mounts, and non-interactive mode exits with an error.

Action order:

1. The command shows a summary of the selected mount.
2. If `-y` is not passed, it asks for confirmation.
3. First it performs `umount` for the selected mount.
4. Only after successful `umount` does it remove the entry from YAML.
5. Before saving, it creates a timestamp backup of the config next to the YAML file.

## See Also

- [Configuration](../configuration.md)
- [Backups](../backups.md)
- [run](run.md)
