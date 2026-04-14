# VM Lifecycle Commands

## Contents

- [`start-vm`](#start-vm)
- [`stop-vm`](#stop-vm)
- [`restart-vm`](#restart-vm)
- [`down`](#down)
- [`destroy-vm`](#destroy-vm)

## Commands

## `start-vm`

Starts the selected VM or all configured VMs.

```bash
agsekit start-vm <vm_name>|--all-vms [--config <path>] [--debug]
```

## `stop-vm`

Stops the selected VM or all configured VMs. If required by the current implementation, active mounts are unmounted first.

```bash
agsekit stop-vm <vm_name>|--all-vms [--config <path>] [--debug]
```

## `restart-vm`

Performs the stop/start sequence for selected targets.

```bash
agsekit restart-vm <vm_name>|--all-vms [--config <path>] [--debug]
```

## `down`

Stops all configured VMs. If configured agents are still running, `agsekit` shows them and asks for confirmation unless `--force` is passed.

On Linux, `down` also first tries to stop the `portforward` systemd service.

```bash
agsekit down [--config <path>] [-f|--force] [--debug]
```

## `destroy-vm`

Deletes a VM from Multipass after confirmation.

```bash
agsekit destroy-vm <vm_name>|--all [--config <path>] [-y] [--debug]
```

## See Also

- [create-vm](create-vm.md)
- [status](status.md)
