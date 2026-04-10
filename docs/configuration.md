# Configuration Reference

`agsekit` uses a YAML file, usually at `~/.config/agsekit/config.yaml`.

Resolution order:

1. `--config <path>`
2. `CONFIG_PATH`
3. `~/.config/agsekit/config.yaml`

## Top-Level Sections

- `global`
- `vms`
- `mounts`
- `agents`

## `global`

Common fields:

- `ssh_keys_folder`: host SSH key location used for VM access.
- `systemd_env_folder`: Linux-only location for `systemd.env`.
- `portforward_config_check_interval_sec`: config reload interval for `portforward`.
- `http_proxy_port_pool.start` / `http_proxy_port_pool.end`: automatic local port range for temporary proxy helpers.

## `vms`

Each VM can define:

- `cpu`
- `ram`
- `disk`
- `cloud-init`
- `proxychains`
- `http_proxy`
- `allowed_agents`
- `port-forwarding`

## `mounts`

Each mount describes:

- `source`
- `vm`
- `target`
- `backup`
- `interval`
- `max_backups`
- `backup_clean_method`
- `allowed_agents`

Mount entries connect the host project directory to its VM path and define backup policy.

## `agents`

Each agent entry can define:

- `type`
- `vm`
- `vms`
- `default-args`
- `env`
- `proxychains`
- `http_proxy`

## Example

```yaml
global:
  ssh_keys_folder: ~/.config/agsekit/ssh

vms:
  agent-ubuntu:
    cpu: 4
    ram: 4G
    disk: 20G

mounts:
  - source: /home/user/project
    vm: agent-ubuntu
    target: /home/ubuntu/project
    backup: /home/user/backups-project
    interval: 5

agents:
  qwen:
    type: qwen
    vm: agent-ubuntu
```

## Related Topics

- `proxychains` and `http_proxy` details live in [networking.md](networking.md)
- backup policy details live in [backups.md](backups.md)
- command behavior lives in [commands/README.md](commands/README.md)

## See Also

- [Getting started](getting-started.md)
- [Networking](networking.md)
- [Backups](backups.md)
