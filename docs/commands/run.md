# `run`

## Purpose

Launch an agent inside the target VM, keeping the project on the host in mounted form and making parallel backups.

## Command

In the simplest form:

```shell
agsekit run <agent_name>
```

With all arguments:

```bash
agsekit run [--vm <vm_name>] [--config <path>] [--workdir <path>] [--proxychains <value>] [--http-proxy <value>] [--disable-backups] [--auto-mount] [--skip-default-args] [--debug] <agent_name> [<agent_args...>]
```

## Important Argument Parsing Rule

All `agsekit run` options must appear before `<agent_name>`. Everything after `<agent_name>` is passed to the agent itself unchanged.

As a result, if you previously used an agent without agsekit, switching to agsekit will not be difficult.

Where you had `claude auth login`, it will now be `agsekit run claude auth login`.

## Workdir Rules

- by default, workdir is the current directory on the host;
- `--workdir` can point to another configured mount path;
- if the selected directory exists and matches a mount from the config, `run` starts in the corresponding path inside the VM;
- if this is a nested subdirectory, the same relative subpath is preserved inside the VM.
- if the selected directory does not exist in an interactive terminal, `run` asks whether to start the agent in a temporary directory inside the VM (`/tmp/run-*`); in this mode no host mount is used and backups are not started.
- if the selected directory exists but is not inside configured mounts, interactive mode offers the same fallback to a temporary directory inside the VM (`/tmp/run-*`).
- in non-interactive mode, a missing workdir or launch outside configured mount folders is considered an error.

## Mount Checks

- if a suitable mount is found but is not yet mounted in Multipass, `run` can mount it before launch;
- `--auto-mount` does this automatically;
- when the selected mount is already active (the folder is mounted), `run` warns if the folder on the host is non-empty,
but the corresponding path inside the VM is empty. This usually indicates a Multipass failure and requires calling `agsekit doctor`

## Runtime Helpers

`run` can also:

- automatically mount the source directory through `--auto-mount`;
- NOT start repeated backups if `--disable-backups` is passed;
- apply agent default arguments if `--skip-default-args` is not passed;
- wrap runtime through `proxychains` or `http_proxy`;
- override `proxychains` through `--proxychains <scheme://host:port>` or disable it through `--proxychains ""`;
- override `http_proxy` in upstream mode through `--http-proxy <scheme://host:port>` or disable it through `--http-proxy ""`.

## Restrictions

Agent launch rights are checked in this order:

1. First `mounts[].allowed_agents`
2. Then `vms.<vm>.allowed_agents`
3. And if no problems were found in either place, the agent starts

## Examples

```bash
cd /path/to/project
agsekit run qwen
agsekit run claude auth login
agsekit run --vm agent-ubuntu codex --sandbox danger-full-access
agsekit run --workdir /path/to/project/subdir qwen
agsekit run --auto-mount --proxychains socks5://127.0.0.1:1080 qwen
agsekit run --http-proxy socks5://127.0.0.1:8181 qwen
```

## See Also

- [Agents](../agents.md)
- [Networking](../networking.md)
- [Backups](../backups.md)
