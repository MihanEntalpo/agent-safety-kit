# Getting Started

This is the shortest practical path to a working `agsekit`.

(If the short path did not work, or you use Windows, read the [installation](install.md) article.)

## Contents

- [1. Installation](#1-installation)
- [2. Create a Config](#2-create-a-config)
- [3. Prepare the Environment](#3-prepare-the-environment)
- [4. Add a Mount](#4-add-a-mount)
- [5. Run an Agent](#5-run-an-agent)
- [6. Check Status](#6-check-status)

## 1. Installation

Create a virtual environment and install the package:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install agsekit
```

You can also install through:

```shell
curl -fsSL https://agsekit.org/install.sh | sh
```

On Windows, use PowerShell:

```powershell
irm https://agsekit.org/install.ps1 | iex
```

## 2. Create a Config

Recommended path:

```bash
agsekit config-gen
```

Alternative:

```bash
agsekit config-example
```

After that, edit `~/.config/agsekit/config.yaml` or pass your own path through `--config`.

Detailed [configuration](configuration.md) description.

## 3. Prepare the Environment

Bring up the whole environment with one command:

```bash
agsekit up
```

What will be done:

- host dependency preparation (on Linux this is snapd and multipass; WSL is not supported);
- VM creation
- VM preparation
- agent installation
- for Linux, systemd service installation

## 4. Add a Mount

Add the project directory:

```bash
agsekit addmount /path/to/project
```

The CLI can fill in reasonable defaults for the path in the VM, backup path, interval, and cleanup policy.

## 5. Run an Agent

Go to the project directory and run the agent:

```bash
cd /path/to/project
agsekit run qwen
```

If backups are enabled and there are no snapshots yet, the first initial backup will be created before the agent starts.

## 6. Check Status

Useful commands after startup:

```bash
agsekit status
agsekit shell
agsekit ssh agent-ubuntu
```

## See Also

- [Configuration](configuration.md)
- [Agents](agents.md)
- [Networking](networking.md)
- [All commands](commands/README.md)
