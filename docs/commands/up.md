# `up`

## Purpose

Run the main bootstrap flow without prompts.

## Command

```bash
agsekit up [--config <path>] [--debug] [--prepare/--no-prepare] [--create-vms/--no-create-vms] [--install-agents/--no-install-agents]
```

## What It Does

Depending on flags, `up` can:

- prepare the host;
- create and prepare all configured VMs;
- install all configured agents into their target VMs;
- on Linux only, install/update the `portforward` systemd service.

## Notes

- At least one stage must stay enabled.
- If the workflow needs a config and none is found, the command fails directly instead of opening config-selection UI.

## Examples

```bash
agsekit up
agsekit up --debug
agsekit up --no-prepare
agsekit up --prepare --no-create-vms --no-install-agents
```

## See Also

- [prepare](prepare.md)
- [create-vm / create-vms](create-vm.md)
- [install-agents](install-agents.md)
- [systemd](systemd.md)
