# `up`

## Purpose

Run the main bootstrap flow without interactive questions.

## Command

```bash
agsekit up [--config <path>] [--debug] [--prepare/--no-prepare] [--create-vms/--no-create-vms] [--install-agents/--no-install-agents]
```

## What It Does

Depending on flags, `up` can:

- prepare the host;
- create and prepare all configured VMs;
- install all configured agents into their target VMs;
- only on Linux, install or update the systemd service for `portforward`.

In practice, this is equivalent to running commands in sequence: `agsekit prepare`, `agsekit create-vms`, `agsekit install-agents`, `agsekit systemd install`

By default, all 4 are launched.

## Notes

- At least one stage must remain enabled.
- If the workflow needs a config and it is not found, the command fails.

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
