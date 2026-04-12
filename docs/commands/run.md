# `run`

## Purpose

Launch an agent inside a target VM while keeping the host project mounted and optionally backed up.

## Command

```bash
agsekit run [--vm <vm_name>] [--config <path>] [--workdir <path>] [--proxychains <value>] [--http-proxy <value>] [--disable-backups] [--auto-mount] [--skip-default-args] [--debug] <agent_name> [<agent_args...>]
```

## Important Parsing Rule

All `agsekit run` options must appear before `<agent_name>`. Everything after `<agent_name>` is passed to the agent unchanged.

## Workdir Rules

- default workdir is the current host directory;
- `--workdir` can point to another configured mount path;
- if the chosen workdir exists and matches a configured mount, `run` starts in the corresponding VM path;
- if it points into a nested subdirectory, the matching relative path is preserved inside the VM.
- if the chosen workdir does not exist in an interactive terminal, `run` asks whether to start in a VM-local temporary directory under `/tmp/run-*`; that mode does not use a host mount and does not start backups.
- if the chosen workdir exists but is outside the configured mounts, interactive mode offers the same VM-local temporary-directory fallback under `/tmp/run-*`.
- in non-interactive mode, a missing workdir is still an error.
- in non-interactive mode, a workdir outside the configured mounts is also an error.

## Mount Checks

- if the matching mount exists but is not mounted in Multipass yet, `run` can mount it first;
- `--auto-mount` performs that step automatically;
- when a selected mount is active, `run` warns if the host folder is non-empty but the corresponding VM path is empty.

## Runtime Helpers

`run` can also:

- auto-mount a configured source directory with `--auto-mount`;
- start repeated backups unless `--disable-backups` is used;
- apply agent default arguments unless `--skip-default-args` is used;
- wrap runtime networking through `proxychains` or `http_proxy`;
- override configured `proxychains` with `--proxychains <scheme://host:port>` or disable it with `--proxychains ""`;
- override configured `http_proxy` in upstream mode with `--http-proxy <scheme://host:port>` or disable it with `--http-proxy ""`.

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
agsekit run --http-proxy socks5://127.0.0.1:8181 qwen
```

## See Also

- [Supported agents](../agents.md)
- [Networking](../networking.md)
- [Backups](../backups.md)
