# Backup Commands

## Covered Commands

```bash
agsekit backup-once --source-dir <path> --dest-dir <path> [...]
agsekit backup-repeated --source-dir <path> --dest-dir <path> [...]
agsekit backup-repeated-mount --mount <path> [--config <path>]
agsekit backup-repeated-all [--config <path>]
agsekit backup-clean <mount_source> [<keep>] [<method>] [--config <path>]
```

## `backup-once`

Creates one snapshot in the destination directory. If nothing changed relative to the previous snapshot, no new snapshot is created.
With `--progress`, Linux hosts pass `--progress --info=progress2` to rsync; macOS and Windows hosts pass only `--progress` to stay compatible with older bundled rsync versions.

## `backup-repeated`

Runs backups on a timer with optional initial-skip behavior.

## `backup-repeated-mount`

Resolves paths and policy from a configured mount entry.

## `backup-repeated-all`

Starts repeated backup loops for every configured mount.

## `backup-clean`

Prunes old snapshots with either `tail` or `thin` policy.

## See Also

- [Backups overview](../backups.md)
- [run](run.md)
