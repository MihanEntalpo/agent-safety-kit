# Networking Commands

## Covered Commands

```bash
agsekit portforward [--config <path>] [--debug]
agsekit ssh <vm_name> [--config <path>] [--debug] [<ssh_args...>]
agsekit shell [<vm_name>] [--config <path>] [--debug]
```

## `portforward`

Maintains configured SSH tunnels and periodically reloads the config to adapt when forwarding rules change.

## `ssh`

Connects to the VM over SSH using the host-side key managed by `agsekit`.

Useful for:

- manual debugging;
- ad-hoc command execution;
- extra forwards such as `-L`, `-R`, and `-N`.

## `shell`

Opens an interactive `multipass shell` session in the selected VM.

## See Also

- [Networking reference](../networking.md)
- [systemd](systemd.md)
