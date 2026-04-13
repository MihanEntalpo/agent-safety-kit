# Networking Commands

## Commands

## `portforward`

```bash
agsekit portforward [--config <path>] [--debug]
```

Maintains configured SSH tunnels and periodically rereads the config to adapt to forwarding rule changes.

## `ssh`

```shell
agsekit ssh <vm_name> [--config <path>] [--debug] [<ssh_args...>]
```

Connects to the VM over SSH using a host-side key managed by `agsekit`.

Allows passing arbitrary ssh keys, like in the regular ssh command.

Typical uses:

- manual debugging;
- ad-hoc command execution;
- additional forwards through `-L`, `-R`, and `-N`.

## `shell`

```
agsekit shell [<vm_name>] [--config <path>] [--debug]
```

Opens an interactive `multipass shell` session in the selected VM; essentially works the same way through ssh, but uses Multipass keys and does not allow passing standard ssh arguments.

## See Also

- [Networking and proxies](../networking.md)
- [systemd](systemd.md)
