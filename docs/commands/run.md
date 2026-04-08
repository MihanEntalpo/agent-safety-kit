# `run`

## Purpose

Launch an agent inside a target VM while keeping the host project mounted and optionally backed up.

## Command

```bash
agsekit run [--vm <vm_name>] [--config <path>] [--workdir <path>] [--proxychains <value>] [--disable-backups] [--auto-mount] [--skip-default-args] [--debug] <agent_name> [<agent_args...>]
```

## Important Parsing Rule

All `agsekit run` options must appear before `<agent_name>`. Everything after `<agent_name>` is passed to the agent unchanged.

## Workdir Rules

- default workdir is the current host directory;
- `--workdir` can point to another configured mount path;
- the chosen workdir must exist and match a configured mount;
- if it points into a nested subdirectory, the matching relative path is preserved inside the VM.

## Runtime Helpers

`run` can also:

- auto-mount a configured source directory with `--auto-mount`;
- start repeated backups unless `--disable-backups` is used;
- apply agent default arguments unless `--skip-default-args` is used;
- wrap runtime networking through `proxychains` or `http_proxy`.

## Restrictions

Agent permission checks are resolved in this order:

1. `mounts[].allowed_agents`
2. `vms.<vm>.allowed_agents`
3. unrestricted

## Examples

```bash
cd /path/to/project
agsekit run qwen
agsekit run --vm agent-ubuntu codex --sandbox danger-full-access
agsekit run --workdir /path/to/project/subdir qwen
agsekit run --auto-mount --proxychains socks5://127.0.0.1:1080 qwen
```

## See Also

- [Supported agents](../agents.md)
- [Networking](../networking.md)
- [Backups](../backups.md)
