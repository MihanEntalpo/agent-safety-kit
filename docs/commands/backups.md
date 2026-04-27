# Backup Commands

By default, you do not need to worry about backups: `agsekit run <agent>` starts backups automatically, and they are made every 5 minutes (by default) while the agent is running.

Nevertheless, backups can be launched "manually" with the available commands if this is needed for some scripts.

All backup commands take `.backupignore` files into account. They are structurally similar to `.gitignore` files and specify what should not be copied.

## Contents

- [`backup-once`](#backup-once)
- [`backup-repeated`](#backup-repeated)
- [`backup-repeated-mount`](#backup-repeated-mount)
- [`backup-repeated-all`](#backup-repeated-all)
- [`backup-clean`](#backup-clean)
- [During `agsekit run`](#during-agsekit-run)

## Commands

Commands with the `--config` argument search for a mount in the YAML config and take part of the parameters from it: `mounts[].source`, `mounts[].backup`, `mounts[].interval`, `mounts[].max_backups`, `mounts[].backup_clean_method`, `mounts[].first_backup`.

## `backup-once`

```shell
agsekit backup-once --source-dir <path> --dest-dir <path> [--exclude <pattern>]... [--progress]
```

Creates one snapshot in the destination directory. If nothing changed compared to the previous snapshot, no new snapshot is created.

Shows backup progress.

Arguments:

- `--source-dir <path>` - source folder on the host.
- `--dest-dir <path>` - folder on the host where the backup chain is stored.
- `--exclude <pattern>` - additional exclusion rule for `rsync`; can be passed several times. Added to rules from `.backupignore`.
- `--progress` - show copy progress bar.

This command does not read mount settings from the config. Paths, excludes, and progress mode are set by command arguments.

Cleanup after snapshot creation is not started here.

## `backup-repeated`

```shell
agsekit backup-repeated --source-dir <path> --dest-dir <path> [--exclude <pattern>]... [--interval <minutes>] [--max-backups <count>] [--backup-clean-method tail|thin] [--skip-first]
```

Starts backups on a timer.

Arguments:

- `--source-dir <path>` - source folder on the host.
- `--dest-dir <path>` - folder on the host where the backup chain is stored.
- `--exclude <pattern>` - additional exclusion rule for `rsync`; can be passed several times. Added to rules from `.backupignore`.
- `--interval <minutes>` - interval between snapshots in minutes. Default: `5`.
- `--max-backups <count>` - how many snapshots to keep after cleanup. Default: `100`.
- `--backup-clean-method tail|thin` - cleanup method. Default: `thin`.
- `--skip-first` - wait one interval first instead of making a snapshot immediately.

If the command is launched manually, `--interval`, `--max-backups`, and `--backup-clean-method` are taken from command arguments. When this command is launched by `agsekit run`, these values are taken from the selected mount in the config.

Cleanup is started after each backup cycle.

## `backup-repeated-mount`

```shell
agsekit backup-repeated-mount --mount <path> [--config <path>]
```

Resolves paths and policy from the configured mount entry.

Arguments:

- `--mount <path>` - `mounts[].source` for which backups should be started. If there is one mount in the config, the argument can be omitted. If there are several mounts, the argument is required.
- `--config <path>` - path to the YAML config. If not specified, `CONFIG_PATH` or `~/.config/agsekit/config.yaml` is used.

The found mount provides:

- `mounts[].source` - source folder.
- `mounts[].backup` - backup chain folder.
- `mounts[].interval` - interval between snapshots.
- `mounts[].max_backups` - how many snapshots to keep.
- `mounts[].backup_clean_method` - cleanup method.

Cleanup is started after each backup cycle.

## `backup-repeated-all`

```shell
agsekit backup-repeated-all [--config <path>]
```

Starts repeated backup loops for all mounts from the config.

Arguments:

- `--config <path>` - path to the YAML config. If not specified, `CONFIG_PATH` or `~/.config/agsekit/config.yaml` is used.

For each `mounts[]` entry, its `source`, `backup`, `interval`, `max_backups`, `backup_clean_method`, and `first_backup` parameters are used.

Cleanup is started after each backup cycle in each started loop.

## `backup-clean`

```shell
agsekit backup-clean <mount_source> [<keep>] [<method>] [--config <path>]
```

Cleans old snapshots by `tail` or `thin` policy.

Arguments:

- `<mount_source>` - source mount folder, that is, the value of `mounts[].source`.
- `<keep>` - how many snapshots to keep. Default: `50`. This value is set by the command argument and is not taken from `mounts[].max_backups`.
- `<method>` - cleanup method: `thin` or `tail`. Default: `thin`. This value is set by the command argument and is not taken from `mounts[].backup_clean_method`.
- `--config <path>` - path to the YAML config. If not specified, `CONFIG_PATH` or `~/.config/agsekit/config.yaml` is used.

From the config, the command takes `mounts[].backup` for the found `mounts[].source`. For the `thin` method, `mounts[].interval` is also used, because the interval affects history thinning.

## During `agsekit run`

If `agsekit run` is started from a mount folder and the `--disable-backups` argument was not passed:

1. `run` resolves the effective first-backup policy in this order: CLI `--first-backup`, CLI `--no-first-backup`, then `mounts[].first_backup` from the config.
2. If there are no snapshots yet in `mounts[].backup`, `run` creates an initial snapshot through an internal call to backup logic. While this backup is being made, the user has to wait.
3. If snapshots already exist and the effective first-backup policy is enabled, `run` also creates one blocking pre-run snapshot before starting the agent.
4. After any blocking snapshot, cleanup is immediately performed according to `mounts[].max_backups` and `mounts[].backup_clean_method`.
5. Then `run` starts the background CLI command `backup-repeated`.
6. The selected mount parameters from the config are passed to `backup-repeated`: `mounts[].source`, `mounts[].backup`, `mounts[].interval`, `mounts[].max_backups`, `mounts[].backup_clean_method`.
7. If the current `run` already made a blocking snapshot, background `backup-repeated` starts with `--skip-first`.

If `run` works in a temporary unmounted folder, backup commands are not started.

If `--disable-backups` is passed, background `backup-repeated` is not started. The initial/pre-run snapshot still follows the rules above.

## See Also

- [Backup overview](../backups.md)
- [run](run.md)
